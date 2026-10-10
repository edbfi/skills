# Runtime capabilities

Let the agent in the current harness select the mechanisms that satisfy this workflow. Do not branch
on provider names or infer the current harness from installed binaries, model names, or project
instruction files. Record known host identity for reproducibility; unknown host identity alone does
not block work. The evaluation runner and model are separate choices whose identity must be verified
for measured comparisons.

## Select available mechanisms

Inspect actual tool catalogs, MCP schemas, available skills, or installed CLI help. A particular
discovery tool name is never required. Discover more capabilities when needed and record changes.
An installed executable proves availability, not that it is the current harness or a suitable runner.

Honor the user's tool, model, and browser-mode choices. "Prefer Exa" permits an explained fallback;
"only Exa" does not. Missing requested capabilities are reported, not silently replaced. Ask only
when a restriction prevents the next necessary step. Discovering a capability does not authorize
installations or account/configuration changes.

| Need | Suitable mechanisms | If unavailable |
|---|---|---|
| Files and command execution | Native tools, CLI, or equivalent MCP/API access | Retain available findings; identify which artifact or check cannot be produced |
| Research | Native search/fetch, user-selected MCP such as Exa, browser, registry client, git, HTTP, pinned local sources | Use another permitted route; leave unsupported claims unverified |
| Independent context | Restricted native worker or fresh runner invocation with declared inputs only | Research may be sequential; blind authorship and measured baselines cannot be simulated in a contaminated context |
| Coding runner | Native execution, CLI, or API/MCP harness with files, coding tools, isolation and completion evidence | Preserve research; checkpoint evaluation as incomplete |
| Toolchain/services | Pinned container or appropriate host tools | Exclude examples that cannot be verified |
| Native skill discovery | Observed project-skill mechanism of the chosen runner | Explicit guidance loading may measure content, not automatic triggering |

A bare completion endpoint without the surrounding coding harness is insufficient. Preflight runner
availability and instruction controls at setup; perform the coding smoke test after version selection
and toolchain pinning. Native workers, parallel execution, search tools, viewers, and `skill-creator`
helpers are conveniences, not universal prerequisites.

## Research choices

Discovery, reading a known URL, rendering a page, and inspecting source are different operations.
Use the user-selected tools for their supported operations; otherwise choose from what is available.
A known URL or local tagged source does not require a search first. Read tool schemas or current
usage guidance instead of guessing tool names or flags. Search/fetch via MCP is as eligible as a
native tool; `research.md` defines the evidence requirements for either.

For `agent-browser` or an equivalent browser, respect headed/headless preferences and use an owned
session. If no mode was requested, use the tool's normal default. Read actual page content for facts;
an interactive-links-only snapshot is insufficient. Record the session as a run resource and close
only resources created exclusively for the run. A different browser is a fallback only when the
user's restrictions permit it.

## Worker boundaries

Verify inherited context, accessible files, automatic instructions, and tools as well as the supplied
prompt. Native workers may inherit parent history. A new session or directory alone is not proof of
independence. Restrict answer-gathering access without disabling the connection to the model itself.

| Role | Inputs | Tools and boundaries |
|---|---|---|
| Probe | Stack, component list | Return text or write scoped output; no research/source-reading tools |
| Component researcher | Stack, component, versions, relevant probe claims | Permitted research tools; integration runs after component facts |
| Task author | Stack, services, `eval-tasks.md` §1 only | Return text/fixtures or write scoped output; no web, source-reading, or general shell tools to obtain answers |
| Task executor | Task fixtures, declared tools/services, selected skill treatment | Isolated coding execution under `eval-tasks.md` §2 |
| Grader | Task, sealed assertions, verified facts, output/logs, scripted results | Read declared inputs only; orchestrator runs checks separately |

Component research may be done sequentially in the orchestrator. A probe must precede research in
its own context. If its independence cannot be established, record it as missing; `research.md`
defines the resulting evidence limits. Do not ask an informed context to ignore answers for blind
authorship or baselines. Without independent author/executor/grader contexts, retain completed work
and mark the dependent phases incomplete. Do not deliver an unmeasured draft as a validated skill.

## Runner and limits

The runner need not be the orchestrating harness. Discover its actual model selection, instruction
sources, skill loading, permissions, limits, and logging before using it. A user-specified model is
not silently substituted. Record requested and runtime-reported identities separately; self-reported
model guesses in prose do not confirm identity. Use `eval-tasks.md` §2 for the complete contract.

Set finite `RUN_TIMEOUT_SECONDS` and `RUN_MAX_ATTEMPTS` (including retries) for coding calls. Choose
them with the existing iteration/repeat budget, and record remaining attempts on resume. Record
`RUN_MAX_COST_USD` separately as a number or null. A monetary cap is mandatory only when the user or
governing instructions require one. An unsupported required cap stops the affected calls; a timeout
is not its replacement. An unset optional cap creates no approval gate. Record how each limit is
enforced and any available cost telemetry.

Use authorization already provided for the task. Optional reporting, validation, and packaging helpers
may be used only after inspecting their availability and compatibility. The builder's own contracts
remain sufficient without them; missing optional helpers do not stop the workflow.
