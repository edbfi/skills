# Tasks, baselines, and evaluation

Baselines tell you what the model writes on this stack with no help. Graded against the facts, they
give two lists: mistakes the skill must correct, and things the model already does right, which the
skill must not restate. The same tasks later measure whether the skill works. Everything here is
built to keep those measurements honest: the task author cannot see the answers, the baseline runner
cannot see the skill, and the grader cannot grade from memory.

## 1. Writing tasks

Spawn one subagent whose only inputs are the stack block, `services`, and this section. It never
reads `research/`. If the task prompts contain the facts ("use the 2024 edition", "use `{id}` path
syntax"), the baseline measures reading comprehension, not knowledge.

Start with 10 to 15 tasks, expanding when needed for component/split coverage. Each is what a
developer on this stack would type into a coding agent: a feature in an existing small project, a
bug to fix, a review of a given file, a new service from scratch. Concrete names, a little context, realistic sloppiness. Not "write a web server"; rather
"add a `POST /orders` endpoint that validates the body, writes to Postgres in a transaction, and
returns 201 with the new id; the handler module is `src/orders.rs`".

Stratify so that:

- every named component is the primary subject of at least one task;
- at least a third of tasks cross component boundaries (handler plus database plus async runtime),
  because idiom errors concentrate at seams;
- at least two tasks are reviews or fixes of provided code, where the baseline must notice a
  problem rather than produce one;
- at least one task requires project setup (manifest, config, lint setup), where tool and version
  choices are visible.

Tag each task with its components and assign a split: roughly two thirds `dev`, one third
`holdout`, with every component appearing in both. Holdout prompts and fixtures are sealed when the
task author delivers them; their assertions are sealed in step 3. Run and adjudicate only
development baselines during drafting. Holdouts run in both configurations only after the candidate
is frozen; their outputs and failures never enter `baseline/mistakes.md` or any revision.

Save as `tasks/evals.json` in skill-creator's format with three extra fields (`name`, `components`,
`split`), and write each prompt with any fixture files to `tasks/<name>/`:

```json
{
  "skill_name": "<stack-slug>-guidelines",
  "evals": [
    {
      "id": 1,
      "name": "orders-endpoint-transaction",
      "prompt": "...",
      "expected_output": "A compiling endpoint with a transactional insert and a 201 response",
      "files": ["tasks/orders-endpoint-transaction/src/orders.rs"],
      "components": ["axum", "sqlx", "integration"],
      "split": "dev",
      "expectations": []
    }
  ]
}
```

Assertions are written in step 3, after research, by you, not by the task author.

## 2. Running a task in isolation

Each run happens in its own directory outside the run tree:
`<root>/_runs/<run-id>/eval-<id>/<config>/run-<N>/`, where `<id>` is the task's integer id from
`evals.json` and `<config>` is `without_skill`, `with_skill`, or `old_skill`. These directory names
are what skill-creator's aggregator and viewer glob (`eval-*`, `run-*`); the task's name lives in
`eval_metadata.json`. The directory contains only the task's fixture files, the compose file for
services if the task needs them, and, for `with_skill`, the skill installed as a project skill at
`.claude/skills/<skill-name>/`. The prompt is the task prompt and nothing more: no paths outside the
directory, no mention of a skill.

A new directory alone is not isolation. Use a disposable container or OS account with a clean
home/configuration, no ancestor instruction files, plugins, user skills, or mounts of research and
prior outputs. Provision authentication separately without copying personal instruction/settings
directories. Inspect effective settings and record the runner configuration before any calls.
Allow only task files, the selected project skill, and explicitly listed toolchain/system/cache
paths. If effective instruction sources cannot be verified, mark isolation unverified and do not
claim a measured skill improvement. Installing a project skill tests real description triggering.

```bash
cd "<root>/_runs/<run-id>/eval-<id>/<config>/run-<N>"
timeout 30m claude -p "$(cat ../../../../../tasks/<name>/task.md)" \
  --model "$MODEL_UNDER_TEST" --setting-sources project \
  --output-format stream-json --verbose --max-budget-usd "$RUN_BUDGET" \
  > transcript.jsonl
```

- The prompt file stays outside the task directory, so it is neither a project file the agent sees
  nor part of `outputs/`. Check `claude --help` for the flags this CLI version supports and record
  them; `--setting-sources project` keeps user and local settings out. Record the model ID each
  run reports and reject comparisons if the actual models differ.
- Unattended runs need permission handling. Prefer running the CLI inside the runner container
  with only the task directory mounted when skipping permission prompts; the directory is disposable
  either way.
- Write `timing.json` with skill-creator's keys `total_tokens`, `duration_ms`, and
  `total_duration_seconds`, plus `model` (the ID the run reported), `exit_status`, `result_status`
  (`complete`, `invalid`, or `contaminated`), and `reason` when not complete. Missing completion
  events, timeouts, budget exhaustion, CLI/tool failures, and a build on an unpinned toolchain are
  invalid runs, not zero-scoring task outputs. An invalid or contaminated run gets no `grading.json`; move
  it to `eval-<id>/<config>/invalid/run-<N>-<attempt>/` with its transcript and `timing.json` but
  without `outputs/`, so neither the aggregator (`run-*`) nor the viewer (`outputs/`) picks it up,
  then retry into a fresh `run-<N>`. Diagnose before retrying; stop after two failed retries.
- Run the development tasks in parallel, as many as the machine and the toolchain cache tolerate.
- After the run, copy the directory's working files to `outputs/` and move the whole thing under
  `baseline/eval-<id>/without_skill/run-<N>/` (phase 2) or
  `skill-workspace/iteration-N/eval-<id>/<config>/run-<N>/` (phase 4). Write `eval_metadata.json`
  with skill-creator's keys `eval_id`, `eval_name`, `prompt`, `assertions` (the frozen expectations)
  plus `split` and `components`, once at `eval-<id>/` for the aggregator and once in each
  `eval-<id>/<config>/` for the viewer, which looks only beside and above a run directory. Every
  `eval-<id>/` holds both configurations; the aggregator takes its configuration order from the
  first one it finds. The viewer lists only top-level files of `outputs/`, so for coding tasks
  share `benchmark.md` and the transcripts rather than relying on its Outputs tab.

### Contamination check

Before grading, scan `transcript.jsonl` for any file read, glob, grep, or shell command whose path
resolves outside the task directory and declared toolchain/system/cache allowlist, and for any
skill/research/other-run access in a `without_skill` run. This supplements the clean-runner setup;
transcripts cannot prove the absence of automatically injected instructions.
A hit voids the run: treat it as invalid (no `grading.json`, `result_status: "contaminated"`) and
re-run it. Also scan `with_skill` transcripts for the trigger signal: a `Skill` tool use naming the
skill, or a `Read` of its `SKILL.md`. A with-skill run with neither is a triggering failure, graded
as such, and the strongest signal that the description needs work (§5, Description optimization).

## 3. Assertions

Write assertions for every task, development and held-out, after research and before any
baseline run, from the facts and never from outputs. Then seal the holdout set by recording three
hashes in `manifest.md`:

```bash
jq -S -c '[.evals[] | select(.split == "holdout")]' tasks/evals.json | shasum -a 256
find tasks/<holdout-name>... -type f | sort | xargs shasum -a 256 | shasum -a 256
shasum -a 256 tasks/check.sh
```

Run them from the run folder; the fixture hash embeds the paths. Holdout prompts, fixtures,
assertions, and `tasks/check.sh` never change after this point; the final iteration's freeze covers
the candidate and the development assertions. Each assertion is a sentence that a script or a
grader can check against the outputs and transcript, with a descriptive name that reads clearly in
the viewer.
Generic assertions apply to every task; derived assertions come from the facts and, for development
tasks only, later from the skill's anti-pattern table.

Generic, scripted:

- The project builds with the pinned toolchain in the container.
- The linter passes with warnings treated as errors, using the configuration the stack names (or the
  chosen default).
- The formatter reports no changes.
- Tests the task asked for exist and pass; tests the task did not ask for are not required.
- Named direct dependencies satisfy selected compatible versions and explicit constraints in the
  facts and `versions.json`; assess transitive dependencies through resolver/build results rather
  than requiring current majors. Added direct dependencies need a task-related reason.
- Language mode or edition in the manifest matches the selected mode and explicit constraints.
- No unused imports, bindings, or dead code; no comment describing something the code beneath does
  not do.

Derived, mostly scripted:

- For each `contradicted` or `cutoff-relevant` fact a task touches: the correct pattern is present
  and the stale one absent, as a grep.
- For each anti-pattern row in the skill (phase 4 onward, development tasks only): the row's grep
  finds nothing. These greps live in `tasks/anti-patterns.sh`, which is neither sealed nor shipped,
  and each names the `m-NN` or facts id the row came from, so it measures the mistake rather than
  obedience to the skill.
- Diagnostic only: whether the relevant routed reference was read. Do not count file reads as
  correctness assertions or as outcomes in ablation.

Grader-judged, kept few:

- The code handles the ordinary failure the task implies (empty input, missing row, cancelled
  request) without panicking or swallowing the error.
- A review task identifies the planted problem.

Store assertions in `tasks/evals.json` under `expectations` and in each task's `eval_metadata.json`.
Keep the generic scripted checks in `tasks/check.sh`, taking the project directory as its argument,
plus a small task-specific script in `tasks/<name>/` where needed, so that every iteration grades
the same way. `check.sh` contains only the stack's own commands, never `docker`, `RUN_ID`, or
`.toolchain/` paths: the caller supplies the environment, the evals as
`docker run ... "${RUN_ID}-runner" scripts/check.sh /work` and the end user's agent directly. Phase 3
copies it unchanged to `skill/scripts/check.sh`, so the agent and the evals run the same command.

## 4. Grading baselines

Spawn an independent grader with the task, frozen expectations, facts folder, `versions.json`,
outputs/transcript, and scripted results. Use an installed compatible grader guide if available.
Apply this rule:

> Your own knowledge of this stack may be out of date in exactly the ways the output is. For every
> failed assertion, cite the facts row or the tool output that establishes the failure. An assertion
> you cannot tie to a facts row or a tool output is graded `unverifiable`, not failed.

Write `grading.json` per run in skill-creator's shape:

```json
{
  "expectations": [{"text": "...", "passed": true, "evidence": "facts row axum-02; cargo build log line 14"}],
  "unverifiable": [{"text": "...", "evidence": "no facts row covers connection pool sizing"}],
  "summary": {"passed": 5, "failed": 1, "total": 6, "pass_rate": 0.83, "unverifiable": 1}
}
```

`expectations` holds only scored assertions (`passed` true or false), because the viewer renders
anything else as a failure; unverifiable ones go in the sibling `unverifiable` array, outside
numerator and denominator, with their count in `summary`. Aggregate
with `python "$SKILL_CREATOR/scripts/aggregate_benchmark.py" <dir> --skill-name <name>` when that
helper exists; it reads `eval-*/<config>/run-*/grading.json` and `timing.json`, ignores extra keys,
and writes `benchmark.json` and `benchmark.md` into `<dir>` (`baseline/` in phase 2,
`skill-workspace/iteration-N/` in phase 4). Its delta is the first configuration minus the second in
the order it finds them (alphabetical within the first eval directory): right for `with_skill`
against `without_skill`, inverted for `old_skill` against `with_skill`, so say which in the notes. The helper writes placeholder `metadata` values
(`executor_model`, `runs_per_configuration`); correct them, and add invalid-run counts and
per-split rates to `benchmark.md` by hand. With a single configuration, as in phase 2, ignore its
second column and delta. Without the helper, write both files in its schema yourself. Report run
spread for repeats.

Then adjudicate development results only. Read each development failure and write `baseline/mistakes.md`:

```md
# Baseline mistakes (model: <model id>, <date>)

| id | mistake | tasks | facts | frequency | severity | skill section |
|---|---|---|---|---|---|---|
| m-01 | Uses `:id` path syntax, rejected at registration in 0.8 | 1, 4, 9 | axum-02 | 3/3 tasks touching routes | breaks build | routing |
| m-02 | Pins tokio 1.2x in Cargo.toml and sqlx 0.6 | 1, 6 | versions.json | 2/2 setup tasks | wrong versions | versions |

## Done correctly without help

- Error handling with `Result` and `?` throughout; `thiserror` for library errors.
- Structured logging with `tracing`; spans around handlers.
```

The second list is binding on phase 3: nothing in it goes into the skill. Resist the urge to add it
"for completeness"; completeness is the bloat.

Grader false positives happen. A failure you cannot reproduce against the facts is dropped, with a
note in the grading file's `evidence`, not promoted to a mistake.

## 5. The iteration loop

Use these settings, with installed compatible skill-creator reporting helpers if available:

- **Configurations.** New skill: `with_skill` vs `without_skill`. Re-run: `with_skill` vs
  `old_skill`, installed from `skill-workspace/skill-snapshot/`, the copy phase 0 made before
  anything edited `skill/`.
- **Repeats.** One run per task per configuration while iterating; three in the final iteration so
  the mean and spread are meaningful. Variance between runs of the same prompt is large enough that
  a single-run delta on one task means little; look at the pattern across tasks.
- **What to read when revising.** The development tasks' transcripts and outputs, the viewer
  feedback, and `benchmark.md`. Not the held-out tasks.
- **Where improvements come from.** A failed assertion with the skill present means the skill either
  did not say it, said it where the agent did not look (routing), or said it in a way the agent
  overrode. Read the transcript to find which before adding text. Repeated work across runs (every
  run writes the same lint config or helper) means the skill should ship that file in `assets/` or
  `scripts/`.
- **Budget.** `$BUILDER_DIR/scripts/token_budget.py` runs every iteration and its numbers go into
  the iteration notes next to the pass rate. A pass-rate gain bought with a large token increase is examined for a
  cheaper version.

### Description optimization

Before ablation, on development tasks only. Write about twenty trigger queries to
`skill-workspace/description/trigger-evals.json` in skill-creator's shape,
`[{"query": "...", "should_trigger": true}]`: coding tasks whose project context establishes the
stack without naming a framework, adjacent-stack near misses, projects using one component outside
this combination, and non-coding questions about the stack. If `run_loop.py` is installed, run it
from a disposable directory that contains an empty `.claude/`: it plants a command stub in the
nearest `.claude/commands/` above its working directory and measures triggering of that stub, not of
the installed project skill, so its result is a candidate description, not a measurement.

```bash
mkdir -p skill-workspace/description/.claude && cd skill-workspace/description
PYTHONPATH="$SKILL_CREATOR" python -m scripts.run_loop \
  --eval-set trigger-evals.json --skill-path ../../skill --model "$MODEL_UNDER_TEST" \
  --max-iterations 5 --results-dir . --report none --verbose
```

It writes `<timestamp>/results.json` under the results directory and, by default, holds out 40%
of the queries (`--holdout`) to pick `best_description`. Apply that description to
`skill/SKILL.md`, then confirm it on the real path: the ablation's `with_skill` runs, which follow
next, must all show the trigger signal (§2). A failure there is fixed and re-confirmed on
development tasks before the freeze. Without the helper, inspect triggering in development
transcripts and revise the description by hand.

### Ablation

Before the final iteration, compare each removable H2 section or reference against the full skill
on the affected development tasks, three runs per condition. Each comparison gets its own
directory, `skill-workspace/ablation/<section-slug>/eval-<id>/<config>/run-<N>/`, with the
configurations `with_skill` (the full candidate) and `without_section` (the variant), so the
aggregator's delta reads full minus variant; aggregate each `<section-slug>/` directory
separately. Run the full candidate once, three runs per task, and copy those runs into every
`<section-slug>/` directory, so the cost is (sections + 1) × tasks × 3. Keeping ablation outside `iteration-N/` keeps it out of the viewer. Repair routing when
removing a reference. Grade task outcomes, not file reads or missing provenance rows in the
temporary variant. Restore after each comparison. Delete content only when outcomes consistently
show no loss; retain guidance when results are noisy or coverage is insufficient. Explicit
constraints and verified compatibility requirements remain even if tasks do not exercise them.
Record the comparisons in `skill-workspace/ablation/ablation.md`.

Ablation is where "it seemed important" meets measurement. Expect to delete more than feels
comfortable.

### Final iteration

Freeze the candidate (including description) and assertions. Run three repeats, all tasks including
held-out, both configurations. Report holdout results separately without revising from them. If
further tuning is needed, disclose the limitation and use newly authored sealed holdouts in a new run.

## 6. Cost control

A full iteration is tasks × configurations × repeats coding runs, each with builds. Order of cuts if
the budget is tight: repeats during iteration (already one), blind comparison (skip entirely),
iterations beyond two, parallelism rather than task count. Do not cut the held-out split, the
scripted assertions, or the ablation; they are what makes the output trustworthy. Description
optimization is many calls but each is a trigger decision rather than a coding run; keep it.

Share the viewer or Markdown benchmark as soon as it is ready. Continue authorized development
work while feedback is pending; a viewer is not a required approval gate.
