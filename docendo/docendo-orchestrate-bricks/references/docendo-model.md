# Docendo model and hours

## Source versus occurrence

The left panel contains reusable source definitions. A source has a name, owner, brick type, participants/resources, color, allocated clock hours in the school year, normal duration in minutes and task-overview visibility. Creating a source does not schedule an occurrence.

Each occurrence has a concrete date and start/end time. Its editor shows **Denne lektion tæller som**, including the accounting category and counted duration. Use this to verify classification; a title does not determine accounting.

Click the source and open **Skemalagte brikker** to inspect its scheduled dates, weekdays, times, calendars and total count. This is the efficient way to establish the impact of a source change across weeks. Source renaming propagates to its occurrences after reload. Changing normal duration affects new placements; in the verified test, existing one-hour occurrences retained their durations when the default changed from 90 to 45 minutes.

Docendo blocks source deletion while it still has scheduled occurrences. Delete only the authorized occurrences first, then the unused source. Deleted occurrences can remain in **Slettede lektioner** and history; cleanup means no active tests, not erasing audit history.

## Three separate accounting levels

1. **Opgaveoversigt** contains the employment norm, overall category allocations and the task rows configured to appear there. Treat the user's official overview as authoritative for assigned work.
2. **Timeopgørelse** compares **Tildelt**, **Skemalagt** and **Forskel**, both by category and by source. Verify its selected school year and displayed date filter separately from the employment period: the default report range can extend beyond that period.
3. **An occurrence** has wall-clock duration and Docendo's own counted category/duration. Calendar occupancy alone cannot establish all contractual totals.

**Klokketimer i skoleåret** is an allocation; **Normal varighed (i minutter)** is a placement default. Do not convert to 45-minute teaching lessons without an explicit Docendo setting or authoritative instruction. In the verified test, two 60-minute occurrences appeared as `2` scheduled clock hours; a 90-minute occurrence showed `1 time 30 minutter` in its editor.

**Vis på opgaveoversigt** controls whether the source appears as a task row. A source hidden from that overview can still appear in Timeopgørelse and contribute scheduled hours. Enabling visibility on the test source made its allocated hours appear in the overview.

Overall category allocations are not necessarily the sum of individual source allocations. Read both levels and report discrepancies; do not rewrite one to force equality with the other.

## Sidebar totals are approximate

The source's `t/år` label is a coarse remaining-hours indicator, not an accurate scheduled total. The inspected client computes it using allocated hours minus `floor(actual_hours)`, then formats to zero decimal places. The zero-allocation test source with a 90-minute occurrence displayed `-1t/år`.

For precise decisions use the report columns and occurrence accounting. Read decimal values as decimal hours, not HH:MM. The UI may render uppercase labels through CSS even when DOM text is mixed case; normalize whitespace/case when waiting for report headings.

## Choosing and proposing sources

Search all relevant categories; category placement need not follow everyday interpretations of a title. Match owner, type, participant scope and intended accounting, not title alone. Preserve existing source defaults unless changing them is part of the request.

If sources are absent or insufficient, inspect the task overview and then propose a minimal set with: name, type/accounting, owner/participants, normal duration, allocation source and visibility. Missing per-source allocations remain unresolved; do not derive them from available gaps, an overall remainder or the length of a proposed schedule.
