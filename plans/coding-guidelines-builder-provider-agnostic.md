# Coding guidelines builder provider agnostic refactor plan

Make `coding-guidelines-builder` executable by any agent environment that provides the capabilities
needed for each phase. Research may use native tools, user-selected MCP servers, a browser such as
`agent-browser`, or direct source retrieval. The orchestrator and evaluation runner may use different
providers. Preserve the builder's evidence, isolation, baseline, holdout, and provenance guarantees.

This change is a refactor of the skill's instructions and execution contracts. It does not implement
a general runner framework or promise that a guideline measured on one model improves every model.
The generated artifact remains portable; its measured benefits remain specific to the recorded
model, runner, and configuration.

Status: implemented on 2026-10-10 with implicit capability discovery, as subsequently requested.
No Codex/Claude detection branch is introduced. Integration results and the outstanding isolated-run
acceptance gap are recorded in
`coding-guidelines/coding-guidelines-builder/evals/portability.md`; the `1.1.0` bump remains pending.

## Existing dependencies

Paths below are relative to `coding-guidelines/coding-guidelines-builder/`.

| Location | Dependency to remove from the core workflow |
|---|---|
| `SKILL.md` | Claude Code/Cowork prerequisite, mandatory `claude` CLI and `skill-creator`, subagent wording, Claude evaluation calls |
| `references/research.md` | Named `WebSearch`/`WebFetch` behavior and mandatory native subagents |
| `references/eval-tasks.md` | `.claude/skills`, Claude flags and transcript events, helper-specific evaluation and description-loop assumptions |
| `references/toolchain.md` | Mandatory Claude installation, authentication variables, and execution recipe |
| `references/workspace.md` | Claude model reporting and dollar-cap flags embedded in the manifest contract |
| `references/skill-layout.md` | Claude triggering claims and `CLAUDE.md` as the only project instruction file |

The five existing Python scripts use standard-library facilities and have no provider dependency.
`token_budget.py` already documents its characters-divided-by-four approximation. Keep their current
behavior unless a specific artifact-contract change requires an adjustment.

## Design decisions

### Capabilities and execution preferences

Add a short `references/runtime.md`, linked from setup, for capability selection and independent
worker contexts. Keep research evidence rules in `research.md` and evaluation contracts in
`eval-tasks.md`; do not duplicate them in the runtime reference.

Keep the existing stack inputs. Accept optional execution preferences separately so a research tool
such as Exa is not interpreted as a dependency of the user's application. Preferences cover research
tools, browser mode, worker mechanism, evaluator, model, and effort. They may arrive as ordinary
language; a new configuration file or mandatory interview is unnecessary.

Distinguish preferences from restrictions: "prefer Exa" permits an explained available fallback;
"use only Exa" does not. An unavailable explicitly requested tool or model is reported without a
silent substitution. Ask only when an unresolved restriction blocks the next required step.

At setup, inspect the capabilities actually exposed by the host. Use tool catalogs, MCP schemas,
installed skills, or CLI help as appropriate; never require a tool named `Discover` or `ToolSearch`.
Discover additional tools when needed and update the manifest when bindings change. Discovery is
not permission to install tools or alter account configuration.

Let the executing agent select suitable mechanisms implicitly. Installed binaries, model names,
and project instruction files do not identify the current harness. Codex and Claude are the primary
validation targets, not branches in the core workflow; a known host identity is only provenance.

Preflight runner availability and instruction controls at setup so likely limitations are visible
before substantial research. The actual coding smoke test follows toolchain selection and pinning;
do not move stack-dependent execution ahead of version research.

| Capability | Required use | Accepted implementation |
|---|---|---|
| Files and command execution | Run artifacts, validators, toolchains, examples | Native tools, CLI, or MCP/API-backed execution with equivalent access |
| Access to primary sources | Research and version verification | Native fetch/search, MCP, browser, registry clients, local pinned sources, git, or HTTP |
| Independent worker contexts | Knowledge probe, blind task author, independent grader | Restricted native workers or fresh runner sessions with only declared inputs |
| Isolated coding runner | Baselines and evaluation | Native execution, CLI, or API/MCP-backed coding harness satisfying the evaluation contract |
| Stack toolchain and services | Compile and check examples and task outputs | Pinned container or suitable host environment |
| Skill discovery and activation evidence | Description and triggering evaluation | The selected runner's observed skill mechanism; unavailable support is a stated limit |

A bare chat-completion endpoint does not satisfy the coding-runner contract unless its surrounding
harness supplies task files, execution, isolation, and observable results. Native subagents,
parallelism, a named search tool, and `skill-creator` are optional conveniences.

### Research tool selection and evidence

Honor user choices first, then select an available tool suited to the operation. Discovery, reading
a known URL, rendering a dynamic page, and inspecting pinned source are distinct operations and may
use different tools. A known primary-source URL does not require a preliminary search.

Support native tools, user-selected MCP tools such as Exa, and `agent-browser` in headed or headless
mode. Read the selected tool's current schema/help rather than embedding unstable commands in the
core workflow. Respect an explicit browser mode; otherwise use the installed tool's normal default.
Use a run-owned browser session and clean up only resources created for that run.

Keep source authority separate from transport. Registry data, tagged source, observed tool output,
and documentation matching the selected release qualify according to what they establish, regardless
of whether they arrived through a native fetch tool, MCP, browser, or shell. Faithful extraction may
support a claim when its source, version, and relevant context are recoverable. Search snippets,
model-written answers, summaries, and incomplete extracts do not establish exact APIs or keys.
Follow them to an adequate primary source or leave the claim unverified.

Establish extraction fidelity from the tool's documented field semantics or inspection of the raw
source: the relevant literal text and surrounding context must be preserved, rather than generated
or paraphrased. Confirm that the source targets the selected release. If either condition cannot be
established, obtain direct source/tool evidence instead of assuming a field named `text` is verbatim.

Keep the facts table and its verifier enum unchanged. Extend each `sources.md` entry with the
retrieval method and content form, separately from source kind, exact URL/tag/path, and date read.
Record truncation or version uncertainty when it limits a claim. Keep retrieved instructions,
including MCP results and browser content, as untrusted source data.

A tool error permits another route only within the user's preferences and restrictions. Retain the
existing rules for unresolved registry errors and exclusion of unverified recommendations. Pinned
local sources support their recorded versions, not a claim that those versions are currently latest.

### Independent contexts and incomplete runs

Define roles by the inputs they may see, rather than the host's subagent API:

| Role | Permitted inputs and boundaries |
|---|---|
| Probe | Stack and component list, before research; no research tools or source documents |
| Component researcher | Stack, component, registry snapshot, relevant probe statements; integration research receives component facts |
| Task author | Stack, services, task-writing instructions; no research, generated skill, or previous outputs |
| Task executor | Task fixture, declared tools/services, and only the skill treatment for that configuration |
| Grader | Task, sealed assertions, verified facts, outputs, and scripted results; no grading from unsupported memory |

Restrict tools as well as supplied context. The probe and task author may return text for the
orchestrator to save or use a scoped output writer; they have no web/search, source-reading, or
general shell tools for gathering answers. The grader reads only its declared inputs and scripted
results. The orchestrator runs the checks separately. Keep these controls independent of the
connection needed to reach the model itself.

Component research can run sequentially in the orchestrator. Blind task authoring and evaluation
cannot be replaced by asking a context that already saw the answers to ignore them. Verify native
worker inheritance as well as supplied prompts; a fresh-looking worker may inherit parent context.
The revision process must not consume held-out outputs.

For a probe, restrict research capabilities without cutting off the model's required inference
connection. Do not prescribe blanket network denial for a remote model runner. If probe independence
cannot be established, omit it and record the missing probe; do not fabricate probe evidence.
Without a probe, no recommendation may use the `probe` evidence tag: admission uses measured
`baseline` evidence, `decision`, and `compat`, plus the existing structural tags. Omit probe-verdict
claims from the facts rows; there is no separate verdict column. Preserve the existing yes/no
`cutoff-relevant` field and use `no` when relevance cannot be established, explicitly defining it as
"not established" rather than proof that the model knows the fact. Record the missing probe and its
coverage limit in the manifest and delivered provenance; continue verifying all named components.

Check requirements at the phase that needs them. If isolated execution or blind authoring is
unavailable, preserve useful research and mark the affected phase incomplete. Do not create measured
baseline claims or deliver a supposedly validated skill. An unmeasured draft is a separate,
explicitly requested outcome and is outside this refactor's default completion path.

### Evaluation runner contract

Retain the task, development/holdout split, fixture, grading, and run-directory conventions. Move
Claude commands, installation, credential names, helper quirks, and activation-event examples into
one optional `references/claude-runner-example.md`. Load it only when that runner is selected.
Validate any recipe against installed help and observed behavior before using it.

For every selected runner, record and verify the following before evaluation calls:

- Runner identity/version, invocation or configuration, requested model and effort, and reported
  model identity. Record unknown values honestly; do not equate a requested alias with a confirmed
  runtime identity or silently substitute a model.
- The isolated workspace, pinned toolchain, services, allowed paths/tools, and effective instruction
  sources. Account for ancestor files, user skills, memory, plugins, hooks, and MCP access. A clean
  directory or transcript scan alone cannot establish isolation. Provision credentials separately
  from personal instruction/configuration directories and never record credential values.
- How task fixtures and prompts are delivered, how outputs are captured, and how completion,
  failures, timeout, and cancellation are detected. A success-looking final message alone is not
  reliable completion evidence.
- Skill installation/loading mechanism and available activation evidence. Smoke-test it in a
  disposable workspace separate from actual evaluation fixtures, then start fresh for real runs.
- Separate wall-clock, monetary, and run-count limits, with units and enforcement mechanism.
  Every runner needs finite wall-clock and run-count bounds. A monetary cap is mandatory only when
  the user or governing instructions require it; do not inherit Claude's `RUN_BUDGET` as a universal
  prerequisite. Otherwise record the monetary limit as unset, or record an optional supported cap.
  A timeout is not a dollar cap. If a required spending limit cannot be enforced, stop before the
  affected calls and report the conflict. An unset optional cap creates no additional approval gate.

Research tools chosen for the orchestrator are not automatically exposed to evaluation workers.
The runner's tool access and network policy are fixed across comparison conditions except for the
intended skill treatment. Probe restrictions do not disable tools needed for actual coding tasks.

Make enforced access boundaries and verified effective instruction sources the primary isolation
evidence. Apply a contamination scan when raw logs expose relevant file/tool events; otherwise record
`scan: not_available`. A scan alone never establishes isolation. Missing scan support does not
invalidate a run whose other evidence establishes the required boundaries, but unknown isolation
does invalidate measurement. Observed contamination invalidates the run regardless of other claims.

### Activation modes and valid comparisons

Use `without_skill`, `with_skill`, and `old_skill` for runs using native skill discovery. Task prompts
remain ordinary coding tasks with no instruction to invoke the skill. Discover the actual supported
skill path; do not substitute another provider's directory.

A runner that supports explicit guidance loading but not native discovery may use `with_instructions`
and, for refreshes, `old_instructions`, compared against the same `without_skill` setup. Make the
entire candidate and its routed references accessible through a recorded loading method. This
measures guidance under explicit loading; it does not validate a description's automatic triggering.
Description optimization is not applicable in that mode and is reported as untested. Apply the same
baseline, provenance, ablation, freeze, and held-out evaluation rules to its content measurements.

Keep the task prompt byte-identical across conditions. Deliver guidance through a separate recorded
instruction channel or project instruction file; allowlist its paths only for the relevant treatment.
Prefer loading the entrypoint with references available on demand. Making files accessible does not
mean injecting every reference into context. If a runner requires eager loading of all text, record
that strategy separately, mark routing/reference-read diagnostics not applicable, and restrict
ablation to content effects. Do not compare eager and on-demand loading as one skill-effect delta.
Include loading mode/strategy and their limits in both the benchmark and delivered provenance.

Native activation evidence is `observed`, `not_observed`, or `unknown`. A missing event proves
`not_observed` only when that event is known to be comprehensively logged by the runner. It otherwise
means `unknown`, not a failed task or zero trigger rate. Keep triggering diagnostics separate from
scripted correctness scores; skill reads are not proof that the task was solved correctly.

Replace the current unconditional "all ablation runs must show the trigger signal" freeze gate.
When telemetry is sufficient, address observed activation misses on development runs within the
existing iteration/budget limits and report unresolved misses separately. Unknown activation does
not block freezing when the remaining gates pass; record activation as unverified in the manifest,
benchmark, provenance, and delivery report. Neither state automatically changes a correctness score.
Such native-discovery comparisons measure the effect of making the skill available, without proving
that its content was loaded. Held-out activation failures never feed description revision.

Compare conditions only under the same runner/version, confirmed model, effort, toolchain, fixtures,
tool access, instruction baseline, limits, isolation, and loading mode. The intended skill content
and presence may differ. Materially unknown identity or isolation prevents a measured improvement
claim. Runner/model changes require fresh baselines, not reuse of old pass rates. Cross-provider
results can be reported separately, without attributing their difference to the skill.

### Artifacts and optional helpers

Own the existing `evals.json`, `eval_metadata.json`, `grading.json`, and trigger-query shapes in
`eval-tasks.md`, with field definitions and examples. Existing helper compatibility is optional.
Document the remaining reporting contract there so no reader needs another distribution's source.

Preserve provider logs as `transcript.raw.<format>` inside the existing run directory; the existing
Claude `transcript.jsonl` remains a supported raw artifact. Do not relabel arbitrary logs as a common
event schema. Add a small `run.json` per run with a schema version, runner identity/configuration,
requested and reported model/effort, loading mode, isolation evidence, activation state/evidence,
limits, raw-log paths, and completion evidence. Store grading and extraction decisions with their
source references so a normalized result can be audited against raw output.

Keep `timing.json` names where meaningful: measured duration, process exit status when applicable,
`result_status`, token usage, and reported monetary cost. Unknown provider metrics use `null` with a
reason; do not invent zero values or sum overlapping cache/token fields. Distinguish provider-reported
totals from any derived estimate. A runner without a process exit code uses completion evidence in
`run.json`. Invalid or contaminated runs retain artifacts, get no scored grading, and follow the
existing exclusion and two-retry limit. Record isolation or identity deficiencies as invalid for
measurement, rather than giving them a low correctness score.

Define `total_tokens` as a provider-reported total with documented semantics, or a derived sum of
verified disjoint categories. Record which basis and formula were used; leave it null when neither
is available. Keep provider categories in the raw record instead of forcing incompatible cache
accounting into one invented formula. Invalid-run retention explicitly includes `run.json`, all raw
logs, and `timing.json`, without a scored `grading.json` or viewer-visible `outputs/` directory.
Unconfirmed model identity stays in run metadata and limits; it cannot populate measured
`mistakes.md` rows merely by labeling their model as unknown.

Define `benchmark.json` and matching Markdown explicitly: schema version; run-configuration identity;
per task/configuration/split valid and invalid counts; scored and unverifiable assertion counts;
mean and spread of repeated pass rates; activation counts by state; and available timing/usage/cost
with sample counts. Name each comparison's two conditions and subtraction direction explicitly.
Unverifiable assertions remain outside scoring denominators; missing metrics remain outside their
aggregates. Preserve separate held-out reporting and avoid merging different runner identities.

Make `skill-creator` optional and record which compatible helpers are actually present. Reporting
must work without its aggregator/viewer. Use the documented schema and explicit arithmetic in the
initial refactor; add a small deterministic reporting helper only if validation exposes a concrete
need. Do not pass null metrics or new configuration names to an old helper without checking its
behavior. Use a compatible projection or the builder's own reporting path instead.

Define manual description optimization against the selected runner's observed activation mechanism.
Optional helper results propose a description; they do not establish native triggering unless tested
through the real mechanism. Folder delivery is sufficient; `.skill` archives and external validators
remain optional. Keep `agents/openai.yaml` as optional host metadata and retain the current content
admission rules, example verification, and approximate token budgets.

## Implementation sequence

The refactor is complete only after all steps below; a wording-only removal of provider names is
insufficient. Bump the builder's metadata version from `1.0.0` to `1.1.0` after validation.

1. **Define runtime selection.** Update `SKILL.md` compatibility, inputs, prerequisites, phase routing,
   and completion limits. Add `references/runtime.md` with capability discovery, user preferences,
   and independent-worker rules. Record optional `SKILL_CREATOR` as absent when unavailable.
2. **Update research.** Revise `references/research.md` for tool selection, sequential research,
   scoped probes, transport-independent evidence, and expanded source records. Preserve component,
   registry, facts, and integration semantics.
3. **Refactor evaluations.** Revise `references/eval-tasks.md` to own its schemas, runner contract,
   activation modes, reporting, and helper-free iteration path. Extract the existing Claude-specific
   recipes to `references/claude-runner-example.md`. Update `references/toolchain.md` to specify
   isolation and pinned execution independently of installation/authentication brands.
4. **Align run records and delivery.** Update `references/workspace.md` for capabilities, runner
   identity, limits, schema versions, missing capabilities, new run artifacts, and invalidation.
   Update `references/skill-layout.md` provenance to identify runner/loading mode and validation
   limits. Replace Claude-specific triggering assertions and project-instruction wording.
   Clarify the scope of model-specific baseline evidence in `references/content-rules.md`.
5. **Preserve existing runs.** Treat old manifests as legacy records, preserve their raw artifacts,
   and identify their Claude-specific recipe without inventing missing effort/isolation data.
   Allow refreshes to reuse applicable verified source facts and skill snapshots. New measurements
   use the new contract; do not silently resume incomplete legacy comparisons or overwrite them.
   Preserve old mistakes as historical observations; they must be reobserved in valid new baselines
   before serving as measured evidence for the refreshed model/runner.
6. **Validate behavior.** Add `evals/portability.md` containing scenario inputs, capability setups,
   observable expectations, and a result template. Execute the applicable checks below and record
   actual coverage before finalizing the metadata version.

The expected production changes are seven existing Markdown files, two new runtime/example
references, and the portability evaluation cases. Scripts, their tests, and host metadata stay
unchanged unless a demonstrated contract issue requires a narrow edit. `run.json` and raw logs fit
inside directories already accepted by `audit_files.py`; do not broaden its allowlist preemptively.

## Validation and acceptance

Exercise behavior and artifacts rather than tests that merely match the new wording. Preserve the
existing delta-only admission, verified examples, sealed holdouts, freeze, ablation, invalid-run
exclusion, cleanup ownership, and refresh invariants throughout.

| Scenario | Expected observation |
|---|---|
| Native search and fetch | Available tools are discovered; primary-source claims and exact versions remain traceable |
| User selects Exa or another MCP | Actual exposed schemas are used; tool choice does not become an application-stack dependency |
| MCP supplies only snippets, summaries, or truncated text | Exact claims remain unverified until adequate evidence is retrieved |
| `agent-browser` headed and headless | Requested mode and run-owned session are honored; versioned page content is read, not inferred from link-only snapshots |
| Known URL or pinned source without search tools | Verification proceeds without requiring a discovery tool; freshness claims stay bounded by evidence |
| Required tool/model is missing | No invented call, installation, or silent substitution; permitted independent work continues |
| Preferred tool fails but another is permitted | Replacement is recorded and satisfies the same evidence requirements |
| No native subagents | Fresh scoped runner contexts preserve blindness; inherited context is detected or recorded as insufficient |
| Task author attempts research | Its tools cannot obtain sources or research artifacts; only the allowed inputs and output channel are available |
| No independent probe | No `probe` evidence is admitted; facts keep the documented schema and provenance records the coverage limit |
| No isolated runner or blind task author | Research is retained; evaluation remains incomplete; no measured skill benefit is claimed |
| Claude runner with and without `skill-creator` | Both use the documented artifact/reporting path; optional helpers do not become prerequisites |
| Non-Claude runner | Invocation, skill path/loading, model, and completion come from actual capabilities, not Claude event names |
| Explicit loading only | `with_instructions` is kept distinct from native discovery; no description-triggering claim |
| Eager explicit loading | Task prompt stays identical; loading strategy is recorded and routing diagnostics are not treated as measured behavior |
| Unknown telemetry or activation | Unknown metrics are not zeros; missing activation evidence is not a false failure |
| Native activation remains unknown at freeze | Other gates still apply; activation is qualified in delivery and does not alter correctness scores |
| Runner lacks a monetary cap | An unset optional cap does not block; an explicit required cap prevents calls until the constraint can be satisfied |
| Contamination, timeout, or unpinned toolchain | Runs are excluded from scores, retain diagnostic artifacts, and obey the retry limit |
| Runner/model/effort changes or legacy resume | Comparisons are invalidated appropriately and new baselines are required |
| Refresh with an existing skill | Old and new candidates are evaluated under the same current runner and loading mode |

Use controlled scenario walkthroughs for failure cases and real smoke runs for available integrations.
The real runner smoke test uses one small fixed coding fixture in isolated no-skill and with-guidance
conditions, with an external build/check; it verifies the execution contract and does not establish a
statistical improvement. Include at least one native-discovery runner to exercise description
observation, alongside a non-Claude runner to establish execution portability.

For implementation acceptance, run both browser modes, an available MCP research route, and Claude
plus one non-Claude runner. When a required integration cannot be exercised, document the exact
gap and leave that acceptance item incomplete rather than claiming it passed. Do not install or
configure integrations solely to make a check green without existing authorization. Full stack
benchmarks remain governed by the builder's original evaluation procedure and the user's budget.

Claude may satisfy the native-discovery requirement; the non-Claude smoke may exercise either
loading mode. If a runner cannot confirm model identity, its smoke can establish execution support
but must demonstrate exclusion from measured improvement claims. Bump to `1.1.0` only after all the
required integration cases above and the repository checks pass; incomplete required cases leave
implementation acceptance and the version bump pending.

Run the repository checks after implementation:

```sh
python3 -B scripts/check-content.py
python3 -I -B -m unittest discover -s coding-guidelines/coding-guidelines-builder/tests
prek run --all-files --hook-stage manual
```

Also validate reference links, exercise the file audit with the new run artifacts, and manually
inspect every remaining provider/helper name. Each occurrence must be an optional example, optional
integration, or host metadata. If scripts change, apply the repository's Python typing requirements
and add only tests for meaningful new behavior. Review the final diff for accidental methodology
changes and ensure no provider-specific permission bypass becomes a universal default.

## Independent review

The written draft was reviewed on 2026-10-10 using Claude CLI `2.1.296`, requested and reported model
`claude-fable-5-1`, with `--effort high`. Tools were disabled. The reviewer received the draft and
current skill, references, metadata, scripts, and validator tests. Its verdict was **ready with
corrections**. The table records verification and revisions made after that review; it does not
represent a second approval of the revised text.

Reviewed draft SHA-256:
`58f8ff5d3a3329b0454bbe19004371d8adbe69ff082b5f89eaf37ec43f1acc7b`.

| Finding | Disposition | Resolution |
|---|---|---|
| Monetary-cap defaults could retain a Claude requirement | Partially accepted | Finite time/run bounds are required; monetary caps are required only by user or governing instructions. Rejected a new blanket acknowledgment gate for an unset optional cap. |
| Explicit loading needs prompt, routing, and access rules | Partially accepted | Task prompts stay identical; instruction channel and treatment paths are recorded. References remain available on demand by default. Routing diagnostics become inapplicable only for eager loading, not every explicit-loading runner. |
| Existing triggering gate conflicts with unknown telemetry | Accepted | Replaced the unconditional gate, separated activation from correctness, and documented qualified freeze/delivery behavior without tuning on holdouts. |
| Contamination checks need a path without event logs | Accepted with correction | Documented enforced access and instruction evidence plus optional log scans. A scan alone cannot substitute for isolation evidence. |
| Task-author blindness needs tool restrictions | Accepted | Added scoped tool access for probe, author, and grader so fresh sessions cannot independently retrieve the answers. |
| Missing probe changes admissible evidence | Partially accepted | Disabled `probe` evidence when absent, documented the coverage limit, and preserved the actual facts schema. Rejected the suggested nonexistent verdict column and an undocumented `unknown` enum value. |
| Faithful extraction needs a checkable meaning | Accepted | Require documented field semantics or raw-source inspection, preserved literal context, and release matching. |
| Discover runner limits earlier | Accepted in part | Setup preflights availability; stack-dependent coding smoke remains after toolchain selection. |
| Token totals and retained invalid-run files need precision | Accepted in part | Defined total-token derivation and retained records. Unconfirmed model identity cannot create measured mistakes, even with an unknown-model header. |
| Version bump needs an acceptance gate | Clarified | Required integration cases and repository checks gate the bump. Did not reduce the planned coverage to one runner. |

Review assumptions checked against the repository: the new run files fit the existing audit
allowlist, the token budget is already approximate, and optional host metadata does not bind the
workflow. Headed-browser availability and non-Claude runtime observability remain implementation
checks rather than claims made by this plan.
