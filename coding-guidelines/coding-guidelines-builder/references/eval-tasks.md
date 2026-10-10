# Tasks, baselines, and evaluation

Baselines identify mistakes the skill must correct and things it must not restate. The same tasks
later measure the skill's effect. Task authors cannot see answers, baseline runners cannot see the
skill, and graders must use evidence.

## 1. Writing tasks

Use an independent author whose only inputs are the stack block, `services`, and this section,
with the tool/context restrictions in `runtime.md`. It never reads `research/` or researches the
answers itself. If the task prompts contain facts ("use the 2024 edition", "use `{id}` path
syntax"), the baseline measures reading comprehension, not knowledge.

Start with 10 to 15 tasks, expanding when needed for component/split coverage. Each is what a
developer on this stack would type into a coding agent: a feature in an existing small project, a
bug to fix, a review of a given file, a new service from scratch. Concrete names, a little context,
realistic sloppiness. Not "write a web server"; rather "add a `POST /orders` endpoint that validates
the body, writes to Postgres in a transaction, and returns 201 with the new id; the handler module
is `src/orders.rs`".

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

Save as `tasks/evals.json` in the builder's schema below and write each prompt with any fixture
files to `tasks/<name>/`. IDs are unique integers, names unique directory slugs, `files` fixture
paths, `components` coverage tags, `split` either `dev` or `holdout`, and `expectations` an array
of assertion strings sealed in §3. `expected_output` describes the requested artifact:

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
`evals.json`. The controller supplies the task prompt from outside the workspace and captures logs
outside the agent's access. Expose only fixture files, selected guidance, and declared tool/service
paths. A service compose file stays in `tasks/<name>/`; the controller starts it with a unique
project (`docker compose -p "${RUN_ID}-e<id>-<config>-r<N>" up -d --wait`) and joins the runner to
its network. The fixture `.env` uses the service hostname. Reset service state for each condition.

### Runner contract

Discover and record the runner/version, invocation, requested model/effort, runtime-reported model,
supported permissions, instruction sources, loading method, completion signals, and limits before
coding calls. Select native execution, a CLI, or an API/MCP coding harness meeting the same contract.
`claude-runner-example.md` is an optional recipe only when that runner is selected.

A new directory alone is not isolation. Use a disposable container/account or equivalent enforced
access controls, with verified effective instructions: no inherited memory, ancestor instructions,
user skills, plugins, hooks, or MCP access to research/other runs. Provision authentication separately
from personal configuration. Record the allowed paths/tools/network and actual pinned toolchain.
Research tools chosen for the orchestrator are not automatically enabled for task executors.
Unknown isolation or model identity invalidates a run for measurement.

Use the same runner/version, model, effort, fixtures, toolchain, tool access, limits, instruction
baseline, and loading strategy across conditions. Only intended guidance presence/content differs.
Changing those settings requires fresh baselines. Compare providers separately; their difference
cannot be attributed to the skill. Record finite wall-clock/attempt limits and optional monetary
caps as defined in `runtime.md`, with enforcement and completion/cancellation evidence. A final
answer saying "done" is insufficient without the runner's completion signal and captured artifacts.

### Loading and activation

| Mode | Configurations | Treatment |
|---|---|---|
| `native` | `without_skill`, `with_skill`, `old_skill` | Discover the runner's supported project-skill path and test actual automatic discovery |
| `explicit` | `without_skill`, `with_instructions`, `old_instructions` | Supply guidance through a separate instruction channel/file; this measures content, not triggering |

Keep the task prompt byte-identical across conditions, with no instruction to invoke a skill.
In explicit mode load the entrypoint and make references available on demand where supported;
allowlist guidance paths only for that treatment. If all content must be injected eagerly, record
strategy `eager` instead of `on_demand`; routing/reference-read diagnostics are not applicable and
ablation measures content effects only. Record mode/strategy in benchmarks and delivered provenance.

Smoke-test loading on a disposable fixture before evaluations, then use fresh task workspaces.
Define activation evidence from actual runner observations: `observed`, `not_observed`, or `unknown`.
Missing events mean `not_observed` only when logging of that event class is known to be complete;
otherwise use `unknown`. For explicit mode use `not_applicable`. Neither a read nor an activation
miss is a correctness assertion. Unknown native activation measures the effect of making the skill
available without establishing that it was loaded.

### Run artifacts

Keep raw logs in their original format as `transcript.raw.<format>`; existing `transcript.jsonl`
is also a raw artifact. Write the following records after the executor exits, never inside its
accessible instruction/fixture set. JSON null denotes unknown, accompanied by a reason.

`run.json` has `schema_version: 1` and these required fields:

| Field | Shape and meaning |
|---|---|
| `runner` | Object: `name`, `version`, `invocation` (string), `settings` (object with instruction sources, tools, paths, network, permissions, toolchain identity) |
| `model` | Object: `requested`, `reported`, `effort_requested`, `effort_reported`; strings or null, with `evidence` identifying trusted runtime/config output |
| `loading` | Object: `mode` (`native`/`explicit`), `strategy` (`on_demand`/`eager`), `guidance_paths` (array; empty in baseline), `channel` (string) |
| `isolation` | Object: `status` (`verified`/`unknown`/`contaminated`), `evidence` (array), `scan` (`checked`/`not_available`) |
| `activation` | Object: `state` (`observed`/`not_observed`/`unknown`/`not_applicable`), `evidence` (array) |
| `limits` | Object: positive `timeout_seconds`, positive total `max_attempts`, `max_cost_usd` (number or null), `cost_required` (boolean), `enforcement` (object) |
| `completion` | Object: `state` (`complete`/`failed`/`timeout`/`cancelled`/`unknown`), `evidence` (array) |
| `raw_logs`, `limitations` | Arrays of run-relative paths and explanatory strings, respectively; retain evidence/derivation references here |

`timing.json` requires `duration_ms`, `total_duration_seconds` (duration/1000), `total_tokens`,
`total_cost_usd`, `model` (reported ID or null), `exit_status` (integer or null for no process),
`result_status` (`complete`/`invalid`/`contaminated`), `reason` (string or null), and
`metric_notes` (object explaining null metrics and token-total basis/formula). Tokens use a documented
provider total or a sum of verified disjoint categories; never sum overlapping cache fields. Retain
raw categories; missing usage/cost is null, not zero. Derived estimates are identified in notes and
kept separate from reported metrics in aggregation.

Missing completion evidence, timeouts, exhausted limits, runner/tool failures, and unpinned builds
are invalid, not zero-scoring task outputs. A task's ordinary compiler/test failure on the correct
toolchain is a scored outcome. Invalid/contaminated runs get no `grading.json`; move their raw logs,
`run.json`, and `timing.json` to `eval-<id>/<config>/invalid/run-<N>-<attempt>/`, without `outputs/`.
Diagnose before retrying fresh; stop after two failed retries or the total attempt limit, whichever
comes first. They never populate measured `mistakes.md` rows.

For valid runs copy working artifacts to `outputs/` under `baseline/eval-<id>/without_skill/run-<N>/`
or `skill-workspace/iteration-N/eval-<id>/<config>/run-<N>/`. Put `eval_metadata.json` at `eval-<id>/`
and each configuration directory: `eval_id`, `eval_name`, `prompt`, `assertions` (frozen expectation
strings), `split`, and `components`, copied from the sealed task record. Paired configurations must
have identical metadata. Parallelize independent development runs only within available capacity.

### Contamination check

Enforced access boundaries and verified instruction sources are primary evidence. Before grading,
scan raw file/tool events when available for access outside the task and declared allowlist, including
research/other-run access and any skill access in `without_skill`. Allow selected guidance only in
the relevant treatment. A hit invalidates the run as contaminated regardless of other claims.
When event logs are unavailable, record `scan: not_available`; verified controls may still establish
isolation. A scan alone never proves it. Unknown isolation excludes measurement even if code builds.

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

- The project builds with the pinned toolchain in the selected execution environment.
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
`.toolchain/` paths: the caller supplies the environment. The controller exposes the checks
read-only after the coding run, through the selected runner, so the coding agent never sees the
sealed assertions; the end user's agent runs the delivered checks directly. Phase 3 copies
it unchanged to `skill/scripts/check.sh`, so the agent and the evals run the same command.

## 4. Grading baselines

Use an independent grader with read-only access to the task, frozen expectations, facts folder,
`versions.json`, outputs/transcript, and scripted results. Enforce the boundaries in `runtime.md`;
the orchestrator runs checks separately. Apply this rule:

> Your own knowledge of this stack may be out of date in exactly the ways the output is. For every
> failed assertion, cite the facts row or the tool output that establishes the failure. An assertion
> you cannot tie to a facts row or a tool output is graded `unverifiable`, not failed.

Write `grading.json` per valid run using this builder-owned contract:

```json
{
  "expectations": [{"text": "...", "passed": true, "evidence": "facts row axum-02; build log line 14"}],
  "unverifiable": [{"text": "...", "evidence": "no facts row covers connection pool sizing"}],
  "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0, "unverifiable": 1}
}
```

`expectations` holds only scored assertions (`passed` true or false); unverifiable ones go in the
sibling `unverifiable` array, outside numerator and denominator. `summary.total` is passed + failed;
`pass_rate` is passed / total, or null when total is zero. Counts must match the arrays.

Use `benchmark-report.md` to write canonical `benchmark.json` and `benchmark.md`, including
coverage, null metrics, invalid attempts, and explicit comparison direction. Reporting helpers are
optional and must preserve that contract.

Then adjudicate development results only. Read each development failure and write
`baseline/mistakes.md`:

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

The second list is binding on phase 3: nothing in it goes into the skill.

Grader false positives happen. A failure you cannot reproduce against the facts is dropped, with a
note in the grading file's `evidence`, not promoted to a mistake.

## 5. The iteration loop

Use these settings; compatible reporting helpers are optional:

- **Configurations.** New skill: `with_skill` vs `without_skill`. Re-run: `with_skill` vs
  `old_skill`, installed from `skill-workspace/skill-snapshot/`, the copy phase 0 made before
  anything edited `skill/`. Explicit loading uses `with_instructions` vs `without_skill`, or
  `with_instructions` vs `old_instructions` for a refresh. Keep the loading strategy fixed.
- **Repeats.** One run per task per configuration while iterating; three in the final iteration.
  Report mean and spread; a single-run delta on one task is insufficient evidence.
- **What to read when revising.** The development tasks' transcripts and outputs, `benchmark.md`,
  and viewer feedback when available. Not the held-out tasks.
- **Where improvements come from.** A failed assertion with the skill present means the skill either
  did not say it, said it where the agent did not look (routing), or said it in a way the agent
  overrode. Read the transcript to find which before adding text. Repeated work across runs (every
  run writes the same lint config or helper) means the skill should ship that file in `assets/` or
  `scripts/`.
- **Budget.** `$BUILDER_DIR/scripts/token_budget.py` runs every iteration and its numbers go into
  the iteration notes next to the pass rate. A pass-rate gain bought with a large token increase is
  examined for a cheaper version.

### Description optimization

Before ablation, on development tasks only and only for observable native discovery. Write about
twenty trigger queries to `skill-workspace/description/trigger-evals.json` as
`[{"query": "...", "should_trigger": true}]`: coding tasks whose project context establishes the
stack without naming a framework, adjacent-stack near misses, projects using one component outside
this combination, and non-coding questions about the stack. Run fresh contexts through the actual
project-skill discovery path. In `description/results.json`, record each query, expected decision,
observed activation state, and supporting events. Revise from observed development misses within
the run budget, then recheck the real discovery path. Helpers may propose descriptions only after
their behavior is inspected; command-stub triggering is not installed-skill triggering.

Unknown activation does not become a failed correctness assertion, an invented triggering rate,
or an unbounded retry loop. If activation remains unobservable, freeze when the other gates pass
and record the limitation in the manifest, benchmark, provenance, and delivery. Explicit loading
skips description optimization and reports automatic discovery as untested. Never tune from holdout
queries or held-out coding results.

### Ablation

Before the final iteration, compare each removable H2 section or reference against the full skill
on the affected development tasks, three runs per condition. Each comparison gets its own
directory, `skill-workspace/ablation/<section-slug>/eval-<id>/<config>/run-<N>/`, with the
configurations `with_skill` (or `with_instructions`, the full candidate) and `without_section`
(the variant), with the same loading strategy. Declare the delta as full minus variant; aggregate
each `<section-slug>/` directory
separately. Run the full candidate once, three runs per task, and copy those runs into every
`<section-slug>/` directory, so the cost is (sections + 1) × tasks × 3. Keeping ablation outside
`iteration-N/` keeps its comparisons separate. Repair routing when
removing a reference. Grade task outcomes, not file reads or missing provenance rows in the
temporary variant. Restore after each comparison. Delete content only when outcomes consistently
show no loss; retain guidance when results are noisy or coverage is insufficient. Explicit
constraints and verified compatibility requirements remain even if tasks do not exercise them.
Record the comparisons in `skill-workspace/ablation/ablation.md`.

### Final iteration

Freeze the candidate (including description) and assertions. Run three repeats, all tasks including
held-out, both configurations. Report holdout results separately without revising from them. If
further tuning is needed, disclose the limitation and use newly authored sealed holdouts in a new run.

## 6. Cost control

A full iteration is tasks × configurations × repeats coding runs, each with builds. Order of cuts if
the budget is tight: repeats during iteration (already one), blind comparison (skip entirely),
iterations beyond two, parallelism rather than task count. Do not cut the held-out split, the
scripted assertions, or the ablation; they are what makes the output trustworthy. Description
optimization applies when native discovery is observable. Count trigger calls, coding calls, and
retries against the declared attempt budget. Reduce scope or checkpoint incomplete work before
exceeding a limit; do not omit mandatory evidence and claim completion.

Share the Markdown benchmark and optional viewer when ready. Continue authorized development
while feedback is pending; a viewer is not an approval gate.
