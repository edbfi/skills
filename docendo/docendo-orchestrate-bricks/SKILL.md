---
name: docendo-orchestrate-bricks
description: Plan, create, place, move, edit, copy, delete and audit Docendo calendar bricks in relation to the user's task overview and scheduled hours. Use for Docendo calendar work and brick automation.
---

# Docendo bricks

Operate Docendo through the signed-in browser using **ego-browser**. Read that skill for connection and page control. Use normal UI forms for exact dates, times and source properties; use the supplied pointer helper for initial placement. Browser evaluation reads DOM data only. Do not mutate framework stores, replay private APIs or export authentication data.

Resolve the installed skill directory before running bundled commands; the relative paths below are relative to that directory, not the user’s project. Keep task plans and audit logs outside the installed skill.

## Establish context and scope

Confirm the selected school, calendar owner, calendar ID, school year and actual school-year period from Docendo. A week number alone is insufficient: record its full date range. Reuse the same browser page throughout.

Distinguish **source definitions**, **scheduled occurrences**, **allocated hours**, **scheduled hours** and **task-overview visibility**. Read [the Docendo model](references/docendo-model.md) before creating sources or making decisions about hours.

Expand relevant source categories before deciding a brick is missing. Reuse matching sources, including their ownership, participants and type. If no suitable sources exist, inspect the task overview and propose definitions consistent with its assignments; do not invent allocations from empty calendar space. Names belong to the user's data, never to the skill's policy. Two sources with the same title require disambiguation.

## Plan

Use the user's source and existing authorization. For multi-occurrence work, keep a JSON plan using [the plan format](references/plans.md). Validate it before writing:

```sh
python3 scripts/validate_plan.py /absolute/path/plan.json
# When the user has selected the four-module profile:
python3 scripts/validate_plan.py /absolute/path/plan.json --profile profiles/four-modules.json
```

Module times and break rules live in the selected profile, separately from Docendo's mechanics. The included [four-module profile](profiles/four-modules.json) is opt-in, not a universal Docendo timetable. Classify each activity from source wording, location and user intent; do not classify it from its name or duration alone. Follow [module and continuous-event rules](references/plans.md#module-and-continuous-events).

## Execute

Read [browser operations](references/browser-operations.md) for the requested operation. Use these canonical paths:

| Intent | Path |
|---|---|
| Create a reusable source | **Opret brik** form |
| Place an occurrence | `placeSource(page, input)` from `scripts/ego_docendo.mjs` |
| Move within/across weeks, or change duration | Occurrence date picker and exact start/end fields, then their **Gem** |
| Repeat a source on selected dates | Place each planned occurrence with its own exact date/time |
| Rename/reconfigure a source | Source editor; first inspect **Skemalagte brikker** for the full affected set |
| Delete one occurrence | Its editor's **Slet lektion**, then confirmation |
| Delete an unused source | Source editor's **Slet brikken** |

Use fresh snapshots to ground unfamiliar controls and fresh DOM measurements for pointer input. Batch known form actions; do not take a screenshot and full snapshot after every click. The helper derives positions and refuses ambiguity, duplicate starts, obscured targets and unapproved overlap before pressing the mouse. It performs one drag, reloads and checks the persisted result. Never run a second drop because a timeout made the first result uncertain.

An approved operation on a defined set is sufficient authorization for that set. Do not repeatedly ask for each occurrence. Limit repairs and cleanup to the authorized scope; temporary test-brick authorization includes cleanup when agreed. Source changes affect all their occurrences and may affect other calendars, so verify the full scope first. Do not alter official allocations merely to reconcile a scheduling discrepancy.

## Verify and report

For each mutation, compare the intended title, date, weekday, start/end, count and applicable module rule. For moves, check both old and new positions. A visible provisional event is not proof of persistence. Reload once for the completed transaction or coherent batch; the placement helper already does this, so do not add another reload. Reload is essential after a source rename because occurrence labels can stay stale.

If a drop, save, date or count differs from the plan, inspect and reconcile the observed state before continuing. Correct exact times through the editor when the created occurrence is unambiguously identified and the requested correction is already authorized. Do not retry an uncertain creation.

After changes affecting hours, read **Timeopgørelse** for the correct period and compare **Tildelt / Skemalagt / Forskel**; after source/visibility changes also check **Opgaveoversigt**. Record discrepancies without silently changing the user's contract. Keep a small task-local audit of planned and observed values, affected scope, persistence and unresolved items. User-specific data and experimental notes do not belong in this reusable skill.

Report what changed and what was verified. Leave no test sources or active test occurrences behind. Do not claim that deleted history/audit records were erased.
