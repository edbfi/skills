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
│   │   ├── evals.json               # skill-creator format plus name, components, split
│   │   ├── check.sh                 # scripted checks every run is graded by
│   │   └── <task-name>/             # task.md and fixture files
│   ├── baseline/
│   │   ├── eval-<id>/
│   │   │   ├── eval_metadata.json
│   │   │   └── without_skill/run-<N>/   # outputs/, transcript.jsonl, timing.json, grading.json
│   │   ├── benchmark.json, benchmark.md
│   │   └── mistakes.md              # adjudicated list; drives the draft
│   ├── examples/                    # one real project; source of truth for every code block
│   ├── skill/                       # the generated skill
│   ├── skill-workspace/             # iteration-N/eval-<id>/<config>/run-<N>/, description/
│   └── .toolchain/                  # tool homes and caches, host mode only
└── _runs/<run-id>/eval-<id>/<config>/run-<N>/   # isolated task directories, eval-tasks.md §2
```

`audit_files.py` holds this set. Run it at the end of every phase; any file it lists is moved into
the layout or declared under `## Additional files` in `manifest.md` with a reason. It also reports
symlinks that resolve outside the run folder. It is read-only; never delete unfamiliar files
automatically.

## manifest.md

The manifest is the cleanup contract and the resume state. Sections:

- **Stack**: the stack block verbatim.
- **Models**: orchestrator, probe subagent, and model under test (the ID `claude -p` runs report),
  with the CLI version and the flags `claude --help` lists.
- **Paths**: `SKILL_CREATOR`, `BUILDER_DIR`, the root.
- **Resources**: one row per image (tag, digest, pre-existing or pulled by this run), volume,
  network, clone, cache, and service, each marked created by this run or pre-existing. Only
  resources marked created exclusively by this run are removed in phase 5.
- **Phases**: one line per phase: `pending`, `done <timestamp>`, or `failed <reason>`, plus the
  task, configuration, and run numbers completed inside phases 2 and 4 so an interrupted
  evaluation resumes without overwriting results.
- **Holdout seal**: SHA-256 of the holdout entries of `tasks/evals.json` and of `tasks/check.sh`,
  written at the end of eval-tasks.md §3.
- **Additional files**: anything outside the layout, with a reason.

Resume a phase marked done only if its inputs and outputs still match the manifest; changed inputs
invalidate every dependent phase.

## Re-runs

Skills go stale in two directions: the stack moves, and the model improves. A refresh with
`existing-skill` set starts a new run folder, copies the old skill to `skill/` and the old
`research/versions.json` to `research/versions-<date>.json`, and costs a fraction of a fresh run:

1. Regenerate the snapshot against the preserved one; never redirect output over the `--previous`
   input:

   ```bash
   python "$BUILDER_DIR/scripts/registry_versions.py" research/components.json \
     --previous research/versions-<date>.json > research/versions.json
   ```

   Re-research the components it lists as changed or removed, their integration seams, changed
   constraints, and previously unresolved facts.
2. Re-probe and re-baseline with the current model under test. Any mistake in `mistakes.md` the
   model no longer makes is demoted out of `SKILL.md` into the relevant reference, or deleted if
   that reference section existed only for it.
3. Run skill-creator's loop with the old skill as the `old_skill` configuration.
4. The expected outcome is a shorter skill. A re-run that only adds content needs a reason in
   `manifest.md`.
