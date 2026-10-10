# Workspace, manifest, and re-runs

Every run gets one folder under a durable root (`~/skill-playground/` by default). Never `/tmp`: it
is wiped at reboot on macOS and lives in memory on several Linux distributions, while toolchains and
caches reach gigabytes.

## Layout

The folder name is the run ID: `<date>_<stack-slug>_<suffix>`, with a short random suffix so two
runs on the same stack and day never collide. The same string is `RUN_ID` for Docker volumes and
networks.

```
<root>/
├── <run-id>/
│   ├── manifest.md
│   ├── research/
│   │   ├── components.json          # component list for registry_versions.py
│   │   ├── probe.md                 # what the model believes before any research
│   │   ├── facts/<component>.md
│   │   ├── clones/                  # narrow clones; deleted in phase 5
│   │   ├── sources.md
│   │   ├── versions.json            # current registry snapshot
│   │   └── versions-<date>.json     # earlier snapshots, kept on re-runs
│   ├── tasks/
│   │   ├── evals.json               # builder schema defined in eval-tasks.md
│   │   ├── check.sh                 # generic scripted checks; sealed with the holdouts
│   │   ├── anti-patterns.sh         # phase 4 greps, development tasks only; never shipped
│   │   └── <task-name>/             # task.md and fixture files
│   ├── baseline/
│   │   ├── eval-<id>/
│   │   │   ├── eval_metadata.json       # task metadata; copied into each <config>/
│   │   │   ├── without_skill/run-<N>/   # outputs/, raw logs, run.json, timing.json, grading.json
│   │   │   └── without_skill/invalid/   # voided runs, kept for diagnosis
│   │   ├── benchmark.json, benchmark.md
│   │   └── mistakes.md              # adjudicated list; drives the draft
│   ├── examples/                    # one real project; source of truth for every code block
│   ├── skill/                       # the generated skill
│   ├── skill-workspace/
│   │   ├── skill-snapshot/          # existing skill; old_skill or old_instructions
│   │   ├── iteration-N/eval-<id>/<config>/run-<N>/
│   │   ├── ablation/<section-slug>/eval-<id>/<config>/run-<N>/
│   │   └── description/             # trigger-evals.json and activation results
│   └── .toolchain/                  # tool homes and caches, host mode only
├── _runs/<run-id>/eval-<id>/<config>/run-<N>/   # isolated task directories, eval-tasks.md §2
└── dist/<stack-slug>/               # delivered skills
```

`audit_files.py` holds this set. Run it at the end of every phase; any file it lists is moved into
the layout or declared under `## Additional files` in `manifest.md` with a reason. It also reports
symlinks that resolve outside the run folder. It is read-only; never delete unfamiliar files
automatically.

## manifest.md

The manifest is the cleanup contract and the resume state. Sections:

- **Stack**: the stack block verbatim.
- **Contract**: `schema_version: 1`, builder version, and artifact schemas from `eval-tasks.md` and
  `benchmark-report.md`.
- **Execution preferences and capabilities**: user choices/restrictions; tools actually selected,
  their discovered schemas/help, worker mechanisms and inherited-context controls; known host
  identity; available reporting helpers. Record changes as capabilities are discovered. No provider
  detection step is required. Record missing probe or other capabilities and affected phases.
- **Models and runner**: orchestrator, probe, task-author, grader, and model under test; requested
  versus runtime-reported IDs and effort. Record runner/version, invocation, instruction sources,
  permissions, tool/network/path boundaries, loading mode/strategy, activation evidence definition,
  and the smoke result. Unknown identity/isolation cannot support a measured improvement claim.
- **Paths and limits**: optional `SKILL_CREATOR` (or absent), `BUILDER_DIR`, absolute `RUN_DIR`,
  root, finite `RUN_TIMEOUT_SECONDS`, total `RUN_MAX_ATTEMPTS`, remaining attempts, and optional
  `RUN_MAX_COST_USD` (number or null). Include units, whether each is required, and enforcement;
  dollars, time, and attempts are not interchangeable. Never record credential values.
- **Resources**: one row per image (tag, digest, pre-existing or pulled by this run), volume,
  network, clone, cache, and service, each marked created by this run or pre-existing. Only
  resources marked created exclusively by this run are removed in phase 5.
- **Phases**: one line per phase: `pending`, `done <timestamp>`, `incomplete <reason>`, or `failed <reason>`, plus the
  task, configuration, and run numbers completed inside phases 2 and 4 so an interrupted
  evaluation resumes without overwriting results.
- **Holdout seal**: the three hashes from eval-tasks.md §3 (holdout entries of `tasks/evals.json`,
  holdout fixture files, `tasks/check.sh`).
- **Additional files**: anything outside the layout, with a reason.
- **Validation limits**: unverified activation, omitted probe, untested components/modes, and other
  limits to preserve in delivered provenance and the report. Missing optional helpers do not imply
  missing evaluation when the builder's reporting path ran successfully.

Resume a phase marked done only if its inputs and outputs still match the manifest; changed inputs
invalidate every dependent phase. Missing required capabilities leave the affected phase incomplete;
continue independent useful work without marking dependent phases done.

Legacy manifests without a schema version retain their original artifacts. Do not invent missing
model, effort, isolation, or instruction-source evidence. Start a new run under this contract for
new measurements, reusing applicable verified facts and the skill snapshot. Old mistakes are
historical observations until reobserved in valid baselines; do not resume an incomplete legacy
comparison as if its settings were known.

## Re-runs

Skills go stale in two directions: the stack moves, and the model improves. A refresh with
`existing-skill` set starts a new run folder, copies the old skill to both `skill/` and
`skill-workspace/skill-snapshot/`, copies the old `research/versions.json` to
`research/versions-<date>.json`, and costs a fraction of a fresh run:

1. Regenerate the snapshot against the preserved one; never redirect output over the `--previous`
   input:

   ```bash
   python3 "$BUILDER_DIR/scripts/registry_versions.py" research/components.json \
     --previous research/versions-<date>.json > research/versions.json
   ```

   Re-research the components it lists as changed or removed, their integration seams, changed
   constraints, and previously unresolved facts.
2. Re-probe when available and re-baseline with the current model under test and runner settings.
   Any mistake in `mistakes.md` the model no longer makes is demoted out of `SKILL.md` into the
   relevant reference, or deleted if that reference section existed only for it.
3. Run the loop in eval-tasks.md §5 with `skill-workspace/skill-snapshot/` as `old_skill`, or
   `old_instructions` for explicit loading. Evaluate old and new candidates with the same current
   runner, model, effort, and loading strategy; never compare historical pass rates across them.
4. The expected outcome is a shorter skill. A re-run that only adds content needs a reason in
   `manifest.md`.
