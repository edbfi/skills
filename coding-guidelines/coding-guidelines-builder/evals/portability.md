# Provider portability checks

This suite checks execution choices and evidence handling. It is not a stack benchmark and does
not establish that generated guidelines improve coding performance. Repeat it when changing the
runtime, research, or evaluation contracts.

## Scenario procedure

Give a fresh context `SKILL.md`, `runtime.md`, `research.md`, `workspace.md`, `eval-tasks.md`, and
its linked `benchmark-report.md`.
Present the situations below without the expected outcomes. Ask for the next action and resulting
artifact qualifications. Compare both the decision and its explanation; do not score keyword
matches. These walkthroughs test interpretation, not enforcement of an actual sandbox.

| Situation | Expected behavior |
|---|---|
| Only Exa permitted; Exa unavailable; native search available | Report the restriction, ask only for the blocked step, do not substitute |
| Exa preferred; fetch fails; permitted complete primary-source fetch available | Record fallback and verify the same release and claim |
| Known versioned URL; headed browser requested; snapshot contains links only | Own a headed session and read page text before verifying |
| Independent probe unavailable | Record omission; no probe evidence; cutoff relevance remains unestablished |
| No native workers; fresh scoped CLI contexts available | Use verified independent contexts without a harness-name branch |
| Executor inherits unknown instructions and can read research | Retain research, leave evaluation incomplete, claim no measured benefit |
| Compatible runner and workers; no skill-creator helpers | Use builder contracts and folder delivery |
| Explicit eager guidance through a separate channel | Same task prompt; automatic discovery untested; routing diagnostics not applicable |
| Native activation unknown; other gates verified | Freeze with qualifications; no correctness penalty or invented trigger rate |
| No dollar cap support; none required | Finite time/attempt limits suffice; optional cap is null |
| User requires a dollar cap the runner cannot enforce | Stop affected calls; timeout is not a substitute |
| Task run times out | Retain invalid diagnostics, no score or measured mistake, bounded retries |
| Requested model ID is the only identity evidence | Reported identity null; exclude measured comparison |
| Refresh changes runner or effort | Fresh baselines; old and new guidance use the same current configuration |
| Token/cost telemetry missing | Null with reasons, never zero |
| Input token total already includes cache hits | Do not add the cache subtotal again |
| Task author has stack-only prompt but unrestricted research access | Blindness not established; restrict tools and accessible inputs |
| Search unavailable; complete known primary-source URL fetchable | Verify directly without requiring search |
| MCP returns summary with relevant context truncated | Exact claim remains unverified until adequate evidence is read |
| One comparison condition lacks planned valid repeats | Delta null; preserve intended task coverage |
| Refresh configuration names sort old before new | Declare comparison direction explicitly, independent of sorting |

Also inspect refresh/legacy manifests, cleanup ownership, frozen holdouts, and unchanged validators
in the diff. A walkthrough does not replace integration runs or the builder's full evaluation loop.

## Integration procedure

1. Inspect the actual MCP schemas and installed CLI help. Record versions and user preferences.
2. Search and fetch a known official versioned page through an available MCP. Inspect returned
   content and truncation; source authority and retrieval transport are separate fields.
3. Read that page in separate owned `agent-browser` sessions, one default headless and one with
   `--headed`. Read page text, inspect session state, and close both owned sessions.
4. Pin a small coding fixture's toolchain and give each runner fresh baseline/treatment workspaces.
   Use this exact task prompt in all conditions, with a trailing newline:

   ```text
   Implement the named export sumNumbers(values) in sum.mjs. It accepts an array of finite numbers and returns their sum, including zero for an empty array. Keep the implementation small and do not add dependencies.
   ```

   Fixture: an exported `sumNumbers(values)` that throws `Error("not implemented")`.
   Guidance: start at zero, accumulate with a `for...of` loop, and return the sum. The native skill
   description targets JavaScript functions aggregating numeric arrays. The explicit condition
   supplies guidance through the runner's separate instruction channel, never in the task prompt.
5. Check syntax externally and assert sums for `[]`, `[1, 2, 3]`, and `[-4, 1.5, 2.5]` are 0, 6,
   and 0. Record completion, runtime model evidence, activation, limits, and raw logs separately.
6. Write `run.json` and `timing.json`. Unknown isolation/model means invalid measurement even when
   code passes. Keep those records and original logs under `invalid/`, with no grading or outputs.
   Run `audit_files.py` on the resulting layout. Never report a performance delta from this smoke.

## Results: 2026-10-10

| Check | Observed result |
|---|---|
| Policy walkthroughs | 21/21 expected decisions and explanations; fresh tool-free Claude invocation, requested/reported `claude-fable-5-1`, requested effort `high` |
| MCP research | Exa search and fetch returned the official Python 3.11 JSON documentation; extracted body contained signatures and examples, with later content truncated |
| Browser modes | `agent-browser` 0.39.0: separate headless and `--headed` sessions each read 26,247 bytes of rendered text from the same page; both closed |
| Claude native execution | Claude Code 2.1.296, requested/reported `claude-fable-5-1`, requested `high`; baseline and treatment completed, all external assertions passed; treatment logged `Skill` for `number-array-guidelines` |
| Codex explicit execution | Codex CLI 0.162.1, requested `gpt-6-astra`/`high`; baseline and eager `AGENTS.md` treatment completed and passed external checks; JSON events did not confirm model identity |
| Toolchain and limits | Node v24.14.0 checked before runs; 240-second controller timeout; six coding calls allocated and consumed; Claude optional cap USD 10/call; no required Codex dollar cap |
| Invalid artifact handling | All host runs excluded; original logs, run records, and timing retained without grading/outputs; three resulting run layouts passed unchanged `audit_files.py` |
| Existing validators | All 22 builder tests passed; loaded files below token ceilings |
| Repository CI set | `uv run --offline --no-project --python 3.13 prek run --all-files --hook-stage manual` passed every hook |
| Optional installed quick validator | Incompatible: rejects the repository's existing `compatibility` frontmatter key; required repository validation remains authoritative |

Research source: [Python 3.11 JSON documentation](https://docs.python.org/3.11/library/json.html).
This was a retrieval smoke, not verification of every statement in the fetched page.

The first Claude pair used `--restricted`; runtime startup did not list the project test skill.
After inspecting that evidence, a fresh pair removed that flag while keeping file-only tools,
`--setting-sources project`, strict MCP configuration, disabled hooks, and `acceptEdits`. Startup
then listed the skill and the treatment invoked it. Both attempts retain their own records;
the discovery correction is not a measured skill improvement. Neither `--restricted` nor the
remaining flags alone established full isolation.

Claude runs used `--output-format stream-json --verbose` and no session persistence. Codex runs used
`exec --ignore-user-config --ignore-rules --ephemeral --skip-git-repo-check --sandbox workspace-write
--json`, with explicit model/effort arguments. These are host smoke configurations, not portable
isolation recipes. The installed CLI help was consulted first.

Task prompt SHA-256: `1c6dc8c88bc518b5d85ff65a0337e3b9390741c024204bed1f9cda77b54b35e1`.
Final Claude treatment raw-log SHA-256:
`64cfec9020b8e1fe4b984a7c257cb954b1bbdd904e3b721d26eb92ecd3773993`.
Codex treatment raw-log SHA-256:
`7ff3f3708463b48e186038ed0b824c0be1895a248930cc3e1d0ef3e4ee607b9d`.
Raw logs are local validation artifacts, not published with the skill.

**Acceptance gap:** Docker's default daemon was unavailable, and full host instruction/filesystem
isolation was not established. These smokes verify execution, discovery, explicit loading, and
exclusion behavior; the isolated paired-run acceptance item remains incomplete. Runtime effort was
not separately confirmed. Keep the planned `1.1.0` bump pending until an isolated paired smoke and
the remaining release checks pass. No end-to-end generated-stack benchmark was attempted.
