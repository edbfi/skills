---
name: coding-guidelines-builder
description: Build a coding-guidelines skill for a specific tech stack (languages, frameworks, libraries, databases, tools, version constraints, minimum targets, exclusions) that tells AI coding agents what current, idiomatic, correct code looks like on that stack. Use this whenever the user hands over a tech-stack description and wants guidelines, a coding standard, rules, a reference, or a skill for agents writing, extending, or reviewing code on that stack, even if they never say "skill". Also use it to refresh, re-verify, or shrink an existing stack skill.
compatibility: Requires file and command access, primary-source research, and a suitable stack toolchain. Measured evaluation requires independent contexts and an isolated coding runner. Native tools, CLIs, APIs, and MCPs may supply these capabilities.
license: AGPL-3.0
metadata:
  author: engels74
  version: "1.0.0"
  vendor: coding-guidelines
---

# Coding Guidelines Builder

A stack skill is loaded into an agent's context in the middle of a coding task, and every token it
occupies is a token the task no longer has. The agent already knows how to program. The only content
that earns its place is the difference between what it would do on its own and what is correct on
this stack today: facts that changed after its training, mistakes it demonstrably makes, and
decisions nobody could infer. The method: research the stack from primary sources; find out what the
model believes and what it writes without help; write only the delta, with examples that compile;
prove each section changes outcomes; cut what doesn't.

## Inputs

The user supplies a stack block. Do not interview beyond filling the gaps below.

```text
stack:
  <platforms, languages, runtimes, frameworks, libraries, databases, servers, package managers,
   type checkers, linters, formatters, tools. Keep version constraints, minimum OS/runtime targets,
   presets, adapters, and "not X" exclusions exactly as written. A tool left unnamed means: pick
   the current maintained default.>
services:
  <external services examples and tests need (database, cache, message broker), or "none">
existing-skill:
  <path to a previously generated skill to refresh, or omit>
```

If `services` is missing, ask once. Everything else in the block is a fact about the stack; never
refer to it as "what the user specified".

Accept optional execution preferences in ordinary language: research tools, browser mode, worker
mechanism, evaluator, model, and effort. These are separate from the application stack. Honor explicit
choices; distinguish a preferred tool from an exclusive restriction.

Record the orchestrator, probe, task-author, grader, and **model under test**, plus the chosen runner
and its configuration, in `manifest.md`. The orchestrating harness and evaluation runner may differ.
Baseline mistakes belong to the tested configuration; a refresh on another model or runner needs
new baselines. Prefer probing the model under test; record differences and treat probe claims as
research hypotheses, not measured task mistakes.

## Prerequisites

- Read `references/runtime.md` during setup. Use the capabilities exposed by the current harness;
  there is no required provider-detection branch. Verify selected tools and worker boundaries.
- File and command access, Python 3 for this builder's scripts, and access to primary sources.
- An isolated coding runner and independent author/grader contexts for measured evaluation.
  Preflight availability at setup; record the specific limit if a later phase cannot run.
- If `skill-creator` is available, its guidance and compatible helpers are optional. Read it before
  using it, record `SKILL_CREATOR`, and inspect its actual helpers. Otherwise record it as absent;
  this builder defines its own evaluation and delivery contracts.
- This skill's directory, recorded as `BUILDER_DIR`. Run its scripts from the run folder as
  `python3 "$BUILDER_DIR/scripts/<name>.py"`.
- Docker, or a host toolchain for platform-bound stacks (Apple SDKs, Windows-only frameworks).
- Network access for research, registries, image pulls, and clones.

## Workspace

`references/workspace.md` holds the run folder layout, the `manifest.md` contract, resume rules,
the file audit, and the re-run procedure.

## Phases

| Phase | Output | Read first |
|---|---|---|
| 0 Setup | run folder, capabilities, `manifest.md`, toolchain availability | `references/runtime.md`, `references/workspace.md` |
| 1 Research | `probe.md`, `facts/`, `sources.md`, `versions.json` | `references/research.md` |
| 2 Tasks and baseline | toolchain installed, `tasks/`, `baseline/`, `mistakes.md` | `references/toolchain.md`, `references/eval-tasks.md` §1-4 |
| 3 Draft | `examples/`, `skill/` | `references/content-rules.md`, `references/skill-layout.md` |
| 4 Evaluate | `skill-workspace/iteration-N/`, frozen `skill/` with its description | `references/eval-tasks.md` §2 and §4-6 |
| 5 Finish | packaged skill copied out, cleanup | this file |

Phases are sequential and checkpointed in `manifest.md`. Changed inputs invalidate dependent phases.

### Phase 0: Setup

Create the run folder and `manifest.md` with the stack block, execution preferences, capabilities,
model/runner records, optional `SKILL_CREATOR`, `BUILDER_DIR`, and the phase table. Check that Docker
or the required host SDK is present; exact
toolchain versions are chosen after phase 1 resolves compatibility and installed before phase 2
runs tasks. If `existing-skill` is set, copy it to `skill/` and to `skill-workspace/skill-snapshot/`
now and follow the re-run procedure in `references/workspace.md`.

### Phase 1: Research

Split the stack into components, probe the model's beliefs without research tools in an independent
context when available, then verify every belief and component against primary sources. Component
research may use scoped workers or proceed sequentially. The outputs are
facts files with a verifier on every claim, and `versions.json` from `registry_versions.py`.
Research produces facts, not prose; nothing from it is copied into the skill.

### Phase 2: Tasks and baseline

An independent task author writes realistic tasks from the stack block and `services` only; it never sees
`research/`. You write the assertions from the facts and seal the holdout set before any task runs.
Baselines execute each development task with no skill through the recorded isolated runner; a
grader with `research/facts/` and the scripted results grades them, and you adjudicate the
development results into `baseline/mistakes.md`.

Two lists come out: the mistakes the model makes, and what it gets right. The second is binding:
anything the baseline did correctly is banned from the skill.

### Phase 3: Draft

Build `examples/` first: a real project on the pinned toolchain in which every pattern the skill
shows is a compiling, linted, tested file. Then write `skill/` from four inputs only:
`baseline/mistakes.md`, the probe findings research contradicted or postdated, the stack's
decisions (tools, configuration, versions), and verified compatibility constraints. Every section
gets a row in `skill/PROVENANCE.md`; `check_provenance.py` fails on sections without one. Code
blocks are copies of files in `examples/`, checked by `verify_examples.py`.

### Phase 4: Evaluate

Use the loop in `references/eval-tasks.md` §5: the same isolated runner and grading as phase 2,
now in both configurations; development tasks
drive iteration and held-out tasks are never read while revising; `token_budget.py` runs every
iteration. Before the final iteration come description optimization where observable and ablation, both on
development tasks. Freeze the candidate, description included, before the holdout evaluation;
never tune on holdout results.

Stop development when the pass rate stops improving, when the user is satisfied, or after three
iterations.

### Phase 5: Finish

1. Confirm the delivered candidate matches the frozen one, description included. Record unresolved
   validation limits in `manifest.md` and the delivery report.
2. Run `token_budget.py skill/`, `check_provenance.py skill/`, `verify_examples.py skill/ examples/`,
   and, when a compatible helper exists, `PYTHONPATH="$SKILL_CREATOR" python -m scripts.quick_validate skill/`
   (it needs PyYAML; if it cannot run, record that as a validation limit).
3. Copy the skill to the user's destination or `<root>/dist/<stack-slug>/`. When
   a discovered compatible `PYTHONPATH="$SKILL_CREATOR" python -m scripts.package_skill <copy> <root>/dist/` runs, deliver
   the `.skill` archive too; if it errors or is absent, deliver the folder and say that no archive
   was produced. Verify the copy matches before cleanup; preserve earlier deliveries.
4. Clean up only resources `manifest.md` marks as created exclusively by this run: services,
   volumes, networks, clones, `_runs/<run-id>/`. Leave shared resources and Docker images. Keep the
   run folder for refreshes.
