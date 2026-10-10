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

Write 10 to 15 tasks. Each is what a developer on this stack would type into a coding agent: a
feature in an existing small project, a bug to fix, a review of a given file, a new service from
scratch. Concrete names, a little context, realistic sloppiness. Not "write a web server"; rather
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
`holdout`, with every component appearing in both. Held-out tasks are run in the baseline and in the
final iteration only, and their outputs are never read while revising the skill.

Save as `tasks/evals.json` in skill-creator's format with two extra fields, and write each prompt
with any fixture files to `tasks/<task-id>/`:

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
`<root>/_runs/<run>/<task-id>/<config>/`, where `<config>` is `without_skill`, `with_skill`, or
`old_skill`. The directory contains only the task's fixture files, the compose file for services if
the task needs them, and, for `with_skill`, the skill installed as a project skill at
`.claude/skills/<skill-name>/`. The prompt is the task prompt and nothing more: no paths outside the
directory, no mention of a skill.

Why `claude -p` and not a Task subagent: a subagent inherits the orchestrator's working directory,
every `CLAUDE.md` up the tree, and user-installed skills. A `claude -p` run from a clean directory
inherits only what is in that directory and the user's global settings. Installing the skill as a
project skill means the with-skill run tests real triggering through the description, which is what
users will experience, rather than a skill path pasted into the prompt.

```bash
cd "<root>/_runs/<run>/<task-id>/<config>"
claude -p "$(cat task.md)" \
  --output-format stream-json --verbose \
  --max-turns 60 \
  > transcript.jsonl
```

- Check `claude --help` for the current flag names; the CLI changes. If a flag exists to restrict
  which settings sources are loaded, use it to exclude user-level skills during baselines; otherwise
  confirm no stack skill is installed user-wide while baselines run.
- Unattended runs need permission handling. Prefer running the CLI inside the toolchain container
  with only the task directory mounted when skipping permission prompts; the directory is disposable
  either way.
- The final `result` event in the stream carries duration and token usage. Write them to
  `timing.json` in skill-creator's format immediately; this replaces the subagent notification that
  skill-creator relies on.
- Run the development tasks in parallel, as many as the machine and the toolchain cache tolerate.
- After the run, copy the directory's working files to `outputs/` and move the whole thing under
  `baseline/<task-id>/` (phase 2) or `skill-workspace/iteration-N/<task-id>/<config>/` (phase 4).

### Contamination check

Before grading, scan `transcript.jsonl` for any file read, glob, grep, or shell command whose path
resolves outside the task directory, and for any read of a `SKILL.md` in a `without_skill` run.
A hit voids the run: record `contaminated` in its grading summary and re-run it. Also scan
`with_skill` transcripts for a read of the skill's `SKILL.md`; a with-skill run that never read the
skill is a triggering failure, graded as such, and the strongest signal that the description needs
work in phase 5.

## 3. Assertions

Write assertions after research and before reading any baseline output. Each assertion is a
sentence that a script or a grader can check against the outputs and transcript, with a descriptive
name that reads clearly in the viewer. Generic assertions apply to every task; derived assertions
come from the facts and, later, from the skill's anti-pattern table.

Generic, scripted:

- The project builds with the pinned toolchain in the container.
- The linter passes with warnings treated as errors, using the configuration the stack names (or the
  chosen default).
- The formatter reports no changes.
- Tests the task asked for exist and pass; tests the task did not ask for are not required.
- Every dependency in the lockfile is within the current major (or the stack's pinned line) per
  `versions.json`; no dependency outside the stack's named set is introduced without a reason in
  the transcript.
- Language mode or edition in the manifest is the current one from the facts.
- No unused imports, bindings, or dead code; no comment describing something the code beneath does
  not do.

Derived, mostly scripted:

- For each `contradicted` or `cutoff-relevant` fact a task touches: the correct pattern is present
  and the stale one absent, as a grep.
- For each anti-pattern row in the skill (phase 4 onward): the row's grep finds nothing.
- Transcript: in `with_skill` runs, the reference file the skill's routing table names for this
  task's components was read.

Grader-judged, kept few:

- The code handles the ordinary failure the task implies (empty input, missing row, cancelled
  request) without panicking or swallowing the error.
- A review task identifies the planted problem.

Store assertions in `tasks/evals.json` under `expectations` and in each run's `eval_metadata.json`.
Keep the scripted checks in `examples/scripts/check.sh` (shipped later with the skill) plus a small
task-specific script per task where needed, so that every iteration grades the same way.

## 4. Grading baselines

Spawn the grader subagent with skill-creator's `agents/grader.md` as its instructions and three
additions: the facts folder and `versions.json` as inputs, the scripted check results already run, and
this rule:

> Your own knowledge of this stack may be out of date in exactly the ways the output is. For every
> failed assertion, cite the facts row or the tool output that establishes the failure. An assertion
> you cannot tie to a facts row or a tool output is graded `unverifiable`, not failed.

Write `grading.json` per run in skill-creator's schema (`text`, `passed`, `evidence`).

Then adjudicate. Read every failure yourself and write `baseline/mistakes.md`:

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

Follow skill-creator's loop with these settings:

- **Configurations.** New skill: `with_skill` vs `without_skill`. Re-run: `with_skill` vs
  `old_skill` (snapshot the existing skill before editing, as skill-creator describes).
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
- **Budget.** `scripts/token_budget.py` runs every iteration and its numbers go into the iteration
  notes next to the pass rate. A pass-rate gain bought with a large token increase is examined for a
  cheaper version.

### Ablation

Before the final iteration, for each H2 section of `SKILL.md` and each reference file: remove it,
run the development tasks once with the skill, grade with scripts only, restore it. A section whose
removal fails no assertion on any task is deleted, or merged into one sentence if it carries a
decision the model could not otherwise know. Record the ablation table in the iteration notes.

Ablation is where "it seemed important" meets measurement. Expect to delete more than feels
comfortable.

### Final iteration

Three repeats, all tasks including held-out, both configurations. Report the held-out numbers
separately; they are the ones that predict use on tasks nobody wrote.

## 6. Cost control

A full iteration is tasks × configurations × repeats coding runs, each with builds. Order of cuts if
the budget is tight: repeats during iteration (already one), blind comparison (skip entirely),
iterations beyond two, parallelism rather than task count. Do not cut the held-out split, the
scripted assertions, or the ablation; they are what makes the output trustworthy. Description
optimization is many calls but each is a trigger decision rather than a coding run; keep it.

Human review is the real bottleneck. Generate the viewer as soon as a run completes and tell the
user roughly how many outputs await them.
