/**
 * Run this function through ego page.evaluate(). It only reads the DOM.
 */
export function inspectDocendoDragState(input) {
  const fail = (message) => {
    throw new Error(`Docendo drag preflight: ${message}`);
  };
  const normalized = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const rectOf = (element) => {
    const rect = element.getBoundingClientRect();
    return {
      x: rect.x,
      y: rect.y,
      width: rect.width,
      height: rect.height,
    };
  };
  const parseTime = (value, label) => {
    const match = /^(\d{2}):(\d{2})$/.exec(String(value || ''));
    if (!match) fail(`${label} must use HH:MM`);
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (hours > 23 || minutes > 59) fail(`${label} is outside 00:00-23:59`);
    return hours * 60 + minutes;
  };
  const isoWeek = (year, month, day) => {
    const date = new Date(Date.UTC(year, month - 1, day));
    const weekday = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - weekday);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
  };

  const {
    sourceTitle,
    targetDate,
    targetTime,
    calendarId,
    schoolYear,
    userName,
    schoolName,
  } = input || {};
  for (const [label, value] of Object.entries({
    sourceTitle,
    targetDate,
    targetTime,
    calendarId,
    schoolYear,
    userName,
    schoolName,
  })) {
    if (!normalized(value)) fail(`${label} is required`);
  }

  const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(targetDate);
  if (!dateMatch) fail('targetDate must use YYYY-MM-DD');
  const [, yearText, monthText, dayText] = dateMatch;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const parsedDate = new Date(Date.UTC(year, month - 1, day));
  if (
    parsedDate.getUTCFullYear() !== year ||
    parsedDate.getUTCMonth() !== month - 1 ||
    parsedDate.getUTCDate() !== day
  ) {
    fail('targetDate is not a real calendar date');
  }

  const schoolYearMatch = /^(\d{4})-(\d{4})$/.exec(schoolYear);
  if (!schoolYearMatch || Number(schoolYearMatch[2]) !== Number(schoolYearMatch[1]) + 1) {
    fail('schoolYear must use consecutive years, for example 2026-2027');
  }
  if (![Number(schoolYearMatch[1]), Number(schoolYearMatch[2])].includes(year)) {
    fail('targetDate is outside schoolYear');
  }

  const calendarLinks = Array.from(document.querySelectorAll('a[href]')).filter((link) => {
    try {
      return new URL(link.href, location.href).pathname === `/calendars/${calendarId}`;
    } catch {
      return false;
    }
  });
  if (calendarLinks.length < 1) fail(`calendar ${calendarId} is not identified on the page`);
  const selectedCalendars = Array.from(document.querySelectorAll('select'))
    .filter((element) => normalized(element.value) === normalized(calendarId));
  if (selectedCalendars.length !== 1) {
    fail(`selected calendar matched ${selectedCalendars.length} controls`);
  }

  const exactTextMatches = (selector, text) => Array.from(document.querySelectorAll(selector))
    .filter((element) => normalized(element.textContent) === normalized(text));
  if (exactTextMatches('h1', userName).length !== 1) fail(`user ${userName} is not unique`);
  if (exactTextMatches('h2', schoolName).length !== 1) fail(`school ${schoolName} is not unique`);

  const sources = Array.from(document.querySelectorAll('.d-cal__subjects__subject')).filter((element) => {
    const title = element.querySelector('.d-cal__subjects__subject__left');
    return normalized(title && title.textContent) === normalized(sourceTitle);
  });
  if (sources.length !== 1) fail(`source title matched ${sources.length} bricks`);
  const sourceRect = rectOf(sources[0]);
  if (
    sourceRect.x < 0 ||
    sourceRect.y < 0 ||
    sourceRect.x + sourceRect.width > innerWidth ||
    sourceRect.y + sourceRect.height > innerHeight
  ) {
    fail('source brick is not fully visible');
  }

  const headerDays = Array.from(document.querySelectorAll('.d-cal__week__header__day'));
  const expectedDayLabel = `${dayText}/${monthText}`;
  const matchingDayIndexes = headerDays
    .map((element, index) => ({ index, text: normalized(element.textContent) }))
    .filter(({ text }) => text.includes(expectedDayLabel));
  if (matchingDayIndexes.length !== 1) fail(`target day matched ${matchingDayIndexes.length} columns`);

  const expectedWeek = isoWeek(year, month, day);
  const weekLabels = Array.from(document.querySelectorAll('.d-cal__week__header__day--weeknumber'));
  if (weekLabels.length !== 1) fail(`week label matched ${weekLabels.length} elements`);
  const weekMatch = /(\d+)/.exec(normalized(weekLabels[0].textContent));
  if (!weekMatch || Number(weekMatch[1]) !== expectedWeek) {
    fail(`visible week does not match ISO week ${expectedWeek}`);
  }
  const rangeHeadings = Array.from(document.querySelectorAll('h3'))
    .filter((element) => normalized(element.textContent).includes(`, ${year}`));
  if (rangeHeadings.length !== 1) fail(`visible year ${year} is not unique`);

  const dayColumns = Array.from(document.querySelectorAll('.days-container__day > .day-cal__event-container'));
  if (dayColumns.length !== headerDays.length) {
    fail(`found ${headerDays.length} day headers but ${dayColumns.length} day columns`);
  }
  const dayIndex = matchingDayIndexes[0].index;
  const targetDay = dayColumns[dayIndex];
  const targetDayRect = rectOf(targetDay);

  const visibleEvents = Array.from(document.querySelectorAll('.day-cal__event'));
  if (document.querySelector('.d-cal--loading')) fail('calendar is still loading');
  const targetDayEvents = Array.from(targetDay.querySelectorAll('.day-cal__event'));
  const exactTargetTitleEvents = targetDayEvents.filter((event) => {
    const title = event.querySelector('.d-cal__event-title');
    return normalized(title && title.textContent) === normalized(sourceTitle);
  });
  const exactTargetTimeEvents = exactTargetTitleEvents.filter((event) => {
    const time = normalized(event.querySelector('.d-cal__event-time__start')?.textContent);
    return time.startsWith(`${targetTime} -`);
  });
  if (exactTargetTimeEvents.length !== 0) {
    fail(`an event named ${sourceTitle} already exists on ${targetDate} at ${targetTime}`);
  }

  const hourItems = Array.from(document.querySelectorAll('.d-cal__week__timed__sidebar > .time'));
  const calendarStartCandidates = hourItems.flatMap((element, index) => {
    const label = normalized(element.textContent);
    if (!/^\d{2}:\d{2}$/.test(label)) return [];
    return [parseTime(label, 'calendar hour label') - index * 60];
  });
  const uniqueStarts = [...new Set(calendarStartCandidates)];
  if (uniqueStarts.length !== 1) fail('calendar start time cannot be derived unambiguously');
  const calendarStartMinutes = uniqueStarts[0];

  const slotElements = Array.from(document.querySelectorAll('.d-cal__week__timed__background > .time-slot'));
  if (slotElements.length < 1) fail('calendar time slots are missing');
  const targetMinutes = parseTime(targetTime, 'targetTime');
  const offsetMinutes = targetMinutes - calendarStartMinutes;
  if (offsetMinutes < 0 || offsetMinutes >= slotElements.length * 30) {
    fail('targetTime is outside the visible calendar range');
  }
  const slotIndex = Math.floor(offsetMinutes / 30);
  const targetSlotRect = rectOf(slotElements[slotIndex]);
  const targetPoint = {
    x: targetDayRect.x + targetDayRect.width / 2,
    y: targetSlotRect.y + targetSlotRect.height * ((offsetMinutes % 30) / 30),
  };
  if (
    targetPoint.x < 0 ||
    targetPoint.y < 0 ||
    targetPoint.x > innerWidth ||
    targetPoint.y > innerHeight
  ) {
    fail('target point is outside the current viewport');
  }

  const fromPoint = {x: sourceRect.x + sourceRect.width / 2, y: sourceRect.y + sourceRect.height / 2};
  if (!sources[0].contains(document.elementFromPoint(fromPoint.x, fromPoint.y))) fail('source is obscured');
  if (!targetDay.contains(document.elementFromPoint(targetPoint.x, targetPoint.y))) fail('target is obscured');
  if (!/^\d{2}:\d{2}$/.test(input.targetEnd || '')) fail('targetEnd is required');
  const endMinutes = parseTime(input.targetEnd, 'targetEnd');
  if (endMinutes <= targetMinutes) fail('targetEnd must follow targetTime');
  if (input.allowOverlap !== true) {
    for (const event of targetDayEvents) {
      const label = normalized(event.querySelector('.d-cal__event-time__start')?.textContent);
      const match = /^(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})$/.exec(label);
      if (!match) fail('target day contains an event with unreadable times');
      if (parseTime(match[1], 'existing start') < endMinutes && parseTime(match[2], 'existing end') > targetMinutes) fail('target interval overlaps an existing event');
    }
  }
  return {
    baselineEventCount: visibleEvents.length,
    baselineExactTargetTitleCount: exactTargetTitleEvents.length,
    baselineExactTargetTimeCount: exactTargetTimeEvents.length,
    baselineTargetDayEventCount: targetDayEvents.length,
    calendarId: String(calendarId),
    dayIndex,
    dayLabel: matchingDayIndexes[0].text,
    sourceRect,
    targetDate,
    targetDayRect,
    targetPoint,
    targetSlotRect,
    targetTime,
    viewport: { width: innerWidth, height: innerHeight, devicePixelRatio },
    week: expectedWeek,
    yearHeading: normalized(rangeHeadings[0].textContent),
  };
}
