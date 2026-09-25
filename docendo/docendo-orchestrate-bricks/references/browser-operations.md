# Browser operations

Use ego-browser's documented API. Keep one TaskSpace/page for the goal and let its skill govern ownership. Authentication is through the normal website. If the landing page offers Uni-login, selecting it can reuse the user's existing SSO session; do not infer that credentials must be entered merely from seeing the landing page.

## Observe and navigate

Use a snapshot for controls; use `page.evaluate` only for read-only DOM extraction and geometry. `readWeek(page)` in `scripts/ego_docendo.mjs` returns visible date labels, week/range and occurrence title/time/type. Wait for the intended week/range after navigation, not just for any calendar header. A header can render before the day columns or events. `.d-cal--loading` and `.day-cal__event__content--loading` signal loading/provisional state.

Week-strip elements have a `content` date-range attribute in the tested client. Read it from the DOM and click that exact range, rather than an ambiguous number such as `12`. Other date controls use `.datepicker-cell[aria-label]` with a full English date and time; inspect the actual attributes rather than inventing timezone strings.

An empty viewport snapshot does not prove a list is empty. Expand categories, use `scope: "full_page"` or extract the relevant DOM list. Prefer a subtree snapshot for an open editor. Read exact input values rather than text presentation. CSS can uppercase report headings without uppercasing DOM text.

## Create and configure a source

Open **Opret brik**. Inspect and fill the source name, owner/participants, annual clock-hour allocation, default duration (minutes), color, school year, brick type and **Vis på opgaveoversigt**. Use only approved values; an empty calendar does not justify choosing contractual allocations. Save once and wait for the source to appear under its category.

For an existing source, click the source row, not a scheduled occurrence. **Skemalagte brikker** lists the full scheduled set; inspect it before source-wide changes. Return to **Redigér brik**, make the approved changes and click **Opdatér brik**. Reload to verify both source and affected occurrences. A changed default duration does not resize existing occurrences. Source renaming changes their titles after reload.

## Place a timed occurrence

Open the target week, confirm its date range and expand the source category. The source's normal duration must match the intended occurrence duration for the helper to return success. If they differ, leave the shared default alone and plan to correct the new occurrence through its editor after inspecting the helper's mismatch report.

Run inside `ego-browser nodejs`, resuming the existing numeric space ID:

```js
const task = await taskSpace(existingSpaceId);
const page = task.page("p1");
const { placeSource } = await import("/absolute/skill/path/scripts/ego_docendo.mjs");
console.log(await placeSource(page, {
  sourceTitle: exactSourceTitle,
  targetDate: isoDate,
  targetTime: startHHMM,
  targetEnd: endHHMM,
  calendarId,
  schoolYear,
  userName: calendarOwnerName,
  schoolName,
}));
```

All variables above come from the checked plan and current UI, not example identities. The helper is imported into the ego Node process; do not execute it in the web page or import Playwright.

It checks selected calendar, owner, school, visible year/week/day, unique source, duplicate start, target interval conflicts, geometry and pointer interception. It hovers the source to bring it into view, then measures afresh. If the target time is outside the viewport, scroll the calendar with the documented browser controls and inspect again **before any drop**. Only pass `allowOverlap: true` for an explicitly intended overlap already reviewed against the plan.

The pointer contract is:

1. `mouse.down` on the source center.
2. A small move inside the source activates Docendo's external drag.
3. Move vertically while still outside the calendar to align with the target time.
4. Cross the calendar columns horizontally and move at least a few pixels inside the destination day.
5. `mouse.up` in `finally` to release the button.

The day-entry handler initializes a provisional occurrence, then subsequent movement activates its drag state. With the normal grid, time snaps to five-minute increments; an enabled bell-time grid can change snapping and duration. Never substitute HTML5 drag events, synthetic page events or direct calls into Docendo's client stores.

The helper waits for the new occurrence, waits for provisional loading to finish, reloads, waits for the returned occurrence and compares the week's before/after tuples. Success means exactly one expected addition with other title/day/time/type tuples unchanged. It does not verify notes, participants or all contractual accounting: inspect those when relevant to the request.

If the helper throws after mouse-down, inspect current state. Do not repeat the drop. If there is exactly one identifiable new occurrence with the wrong snapped time/default duration, open that occurrence and set the intended values. A timeout can occur after a successful write.

## Move and resize precisely

Open the exact occurrence in its day column using date, title and current time to disambiguate. Do not rely on the last title match across the whole page.

Click the displayed date in the occurrence editor to open its date picker. The resulting date textbox is readonly: select the target date cell, using the month arrows when necessary. This works across weeks and months. The calendar behind the editor stays on the original week.

Fill both ordinary time fields. Click the **Gem** next to the date/time controls; it saves the changed date as well as the times. The editor can close automatically after saving: inspect before trying its old close ref. Navigate to the destination week, reload once and confirm the exact occurrence and absence at the original position.

To change duration, edit end time in this same workflow. This is the canonical precise method; pointer snapping is unnecessary for ordinary moves and duration edits.

## Pointer behavior when the task specifically requires it

These native gestures were exercised on test occurrences. Derive rectangles immediately before a gesture; never reuse coordinates after scrolling, navigation or layout changes.

- **Move:** press in the occurrence content, away from the resizer edges, move into the target day and release. Moving horizontally preserves time if the y coordinate stays constant.
- **Resize:** the bottom `.d-event__resizer` adjusts end time. The normal calendar has one `.time-slot` per 30 minutes. Five-minute snapping uses a floor operation, so coordinate rounding can change the result. Verify in the editor and use exact fields to correct it.
- **Copy to adjacent days:** the thin right `.d-event__side__resizer` creates occurrences in the traversed destination days and leaves the original. One adjacent-day copy was verified with the same title, time and counted duration. Do not drag across intermediate days unless those additional occurrences are intended. Notes, substitutes and other metadata require their own verification when copying matters beyond title/time.

For arbitrary selected dates or repeated module schedules, use the validated occurrence plan and `placeSource` per occurrence. This avoids depending on a whole-week selection UI and gives a checked result for each date.

## Delete

For a single occurrence, verify its title/date/time in the editor. Click the editor's **Slet lektion** control (`.dialog-header__bin` in the tested DOM), then **Slet** in the confirmation dialog. Wait for its disappearance and verify persistence. Do not confuse it with the toolbar's delete-day/week control.

For an unused source, open its source editor and click **Slet brikken**. In the tested client this deletes directly without a second confirmation. While scheduled occurrences exist, the delete control is disabled with a message explaining why. Check **Skemalagte brikker** first; deleting a source is not a shortcut for deleting an arbitrary subset of its occurrences.
