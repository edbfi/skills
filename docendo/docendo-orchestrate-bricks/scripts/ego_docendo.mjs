import { inspectDocendoDragState } from './docendo_dom.mjs';

// Only DOM-visible calendar data. No framework stores, cookies or API calls.
export function readWeekDOM() {
  const text = (e) => e?.textContent.replace(/\s+/g, ' ').trim() || '';
  const headers = [...document.querySelectorAll('.d-cal__week__header__day')];
  return {
    loading: !!document.querySelector('.d-cal--loading, .day-cal__event__content--loading'),
    week: text(document.querySelector('.d-cal__week__header__day--weeknumber')),
    range: [...document.querySelectorAll('h3')].map(text),
    events: [...document.querySelectorAll('.days-container__day > .day-cal__event-container')]
      .flatMap((day, index) => [...day.querySelectorAll('.day-cal__event')].map((event) => ({
        day: text(headers[index]),
        title: text(event.querySelector('.d-cal__event-title')),
        time: text(event.querySelector('.d-cal__event-time__start')),
        type: event.getAttribute('data-subject-type'),
      }))),
  };
}

export async function readWeek(page) {
  await page.waitForSelector('.d-cal__week__header__day');
  await page.waitForFunction(() =>
    !document.querySelector('.d-cal--loading, .day-cal__event__content--loading') &&
    [...document.querySelectorAll('h3')].some(e => /\d{4}/.test(e.textContent)) &&
    document.querySelectorAll('.days-container__day > .day-cal__event-container').length > 0 &&
    document.querySelectorAll('.days-container__day > .day-cal__event-container').length === document.querySelectorAll('.d-cal__week__header__day').length);
  return page.evaluate(readWeekDOM);
}

// Call only after the user-authorized plan and source definition are checked.
// A mismatch stops the transaction: inspect/edit the new event, never drop again.
export async function placeSource(page, input) {
  await readWeek(page);
  const selector = `.d-cal__subjects__subject:has-text(${JSON.stringify(input.sourceTitle)})`;
  await page.hover(selector, { label: 'Find kildebrik til placering' });
  // Allow the hover's scrolling/layout to settle before measuring geometry.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)))));
  const probe = await page.evaluate(inspectDocendoDragState, input);
  const before = await readWeek(page);
  const from = {
    x: probe.sourceRect.x + probe.sourceRect.width / 2,
    y: probe.sourceRect.y + probe.sourceRect.height / 2,
  };
  const to = probe.targetPoint;
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  try {
    await page.mouse.move(from.x + 8, from.y, { steps: 4 });
    await page.mouse.move(from.x + 8, to.y, { steps: 12 });
    await page.mouse.move(to.x, to.y, { steps: 24, label: 'Placér brik på valgt tidspunkt' });
    // Day entry initializes the provisional event. Further movement commits drag mode.
    await page.mouse.move(to.x + 4, to.y, { steps: 2 });
  } finally {
    await page.mouse.up();
  }
  await page.waitForFunction(({ title, baseline }) =>
    [...document.querySelectorAll('.day-cal__event')].filter(e =>
      e.querySelector('.d-cal__event-title')?.textContent.trim() === title).length > baseline,
    { title: input.sourceTitle, baseline: before.events.filter(e => e.title === input.sourceTitle).length },
    { timeout: 8000 });
  await page.waitForFunction(() => !document.querySelector('.d-cal--loading, .day-cal__event__content--loading'));
  await page.reload();
  await page.waitForFunction(({ title, count }) =>
    [...document.querySelectorAll('.day-cal__event')].filter(e =>
      e.querySelector('.d-cal__event-title')?.textContent.trim() === title).length >= count,
    { title: input.sourceTitle, count: before.events.filter(e => e.title === input.sourceTitle).length + 1 },
    { timeout: 8000 });
  const after = await readWeek(page);
  const expected = {
    day: probe.dayLabel,
    title: input.sourceTitle,
    time: `${input.targetTime} - ${input.targetEnd}`,
  };
  const matches = after.events.filter(e => e.day === expected.day && e.title === expected.title && e.time === expected.time);
  const remaining = after.events.slice();
  const added = remaining.findIndex(e => e.day === expected.day && e.title === expected.title && e.time === expected.time);
  if (added >= 0) remaining.splice(added, 1);
  const key = e => JSON.stringify(e);
  const unchanged = JSON.stringify(remaining.map(key).sort()) === JSON.stringify(before.events.map(key).sort());
  if (matches.length !== 1 || !unchanged || after.week !== before.week || JSON.stringify(after.range) !== JSON.stringify(before.range)) {
    throw new Error(`Drop needs inspection; do not retry. ${JSON.stringify({ expected, before, after })}`);
  }
  return { verified: true, expected, after };
}
