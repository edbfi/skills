# Plans and configurable module policy

Plans and personal mappings are task-local files. The reusable skill contains no personal brick titles, calendar IDs, school names or user names.

```json
{
  "school_year": "2026-2027",
  "calendar_id": "<read from the selected calendar>",
  "period": {"start": "2026-08-01", "end": "2027-07-31"},
  "events": [
    {
      "title": "<exact existing source title>",
      "date": "2027-03-22",
      "start": "09:00",
      "end": "09:40",
      "source": "<authoritative source or user instruction>",
      "layout": "module"
    }
  ]
}
```

Read the real period from Docendo; the dates above are examples. `period.end` is inclusive. The validator rejects invalid dates/times, dates outside that period, invalid school-year labels, exact duplicates and end times before start times. All overlaps, including enclosing and all-day overlaps, are review warnings. They do not automatically permit an overlapping browser write.

Each row describes an intended occurrence. For moves, deletions and source changes, record the original identity and intended outcome in the accompanying audit; the validator validates planned occurrence values, not permissions or live state.

## Module and continuous events

The included four-module profile specifies 08:10–09:40, 10:10–11:40, 12:15–13:45 and 14:00–15:30. Its intervening gaps are breaks. Other users can supply a JSON profile with their own ordered, nonoverlapping `modules`, or omit the profile when no module policy applies.

With a profile, explicitly classify each occurrence:

- `layout: "module"`: the entire occurrence must fit inside one module. Represent module-structured school work as one occurrence per occupied module. A full school day becomes four occurrences under the included profile. Split 09:00–11:40 into 09:00–09:40 and 10:10–11:40; retain the source's partial outer times.
- `layout: "continuous"`: preserve an explicitly continuous course, conference, off-site activity or other user-confirmed exception. Include `classification_source` explaining the source wording or user decision. A meeting entirely outside school hours can use this classification when appropriate.

All-day status uses `"all_day": true` and omits `start` and `end`. It is incompatible with module layout. Do not invent times from “hele dagen”; establish whether it means the module-structured school day or an actual continuous/all-day activity. Duration alone does not resolve ambiguity.

The validator accepts all-day plans, but the pointer helper places timed occurrences only. An all-day source item must remain unresolved until Docendo's actual all-day control and the requested behavior are established; never silently convert it to a midnight-to-midnight or first-to-last-module timed event.

Rules attach to activity classification or an optional user's source mapping, not names embedded in the skill. A user mapping may associate a uniquely identified source with `module` or `continuous`, but ambiguous items still require clarification.
