# Optional Claude Code runner example

Read this only when Claude Code is the selected evaluation runner. The core contracts are in
`runtime.md`, `toolchain.md`, and `eval-tasks.md`; this recipe does not select the orchestrating
harness. Check `claude --version` and `claude --help` for the installed release before using flags.

## Task invocation

For native discovery, install the candidate as a project skill at `.claude/skills/<skill-name>/`
when supported by the installed runner. Keep the same normal task prompt in both conditions. A
`Skill` event naming the skill or a read of its `SKILL.md` may establish activation; first inspect
actual logs and effective settings. Do not infer a missed trigger from incomplete telemetry.

Inside a disposable runner environment whose filesystem and instruction sources have already been
verified, a command shape is:

```bash
timeout "$RUN_TIMEOUT_SECONDS" claude -p \
  --model "$MODEL_UNDER_TEST" --effort "$RUN_EFFORT" \
  --setting-sources project --strict-mcp-config \
  --output-format stream-json --verbose \
  < "$TASK_PROMPT_FILE" > "$RAW_TRANSCRIPT"
```

The controller supplies the prompt and captures logs outside the agent's accessible workspace;
the command illustrates redirection, not a reason to mount the research/run tree. `timeout` is
coreutils (`gtimeout` on some macOS hosts). Supply vetted unattended permission/tool controls for
the task; the example alone does not establish them. A permission-bypass flag is not isolation and
is never the host default. Restrict tools and writes through the actual environment's controls.

Where supported, add `--max-budget-usd` only for a selected monetary cap; it does not replace the
wall-clock/attempt limits. Inspect completion and error events, exit status, model reports, and
token-field semantics before filling the builder's records. Keep raw categories rather than summing
every number under `usage` (cache categories may overlap).

`--setting-sources project` excludes certain settings, not necessarily all inherited instructions.
Inspect instruction files, memory, plugins, hooks, and skills separately. Flags such as
`--safe-mode` or `--disable-slash-commands` may disable the very skill discovery under test; verify
their behavior instead of combining them blindly with a native-discovery evaluation.

## Installation and authentication

Install the recorded CLI version in the pinned execution environment using a supported installation
method. A release distributed through npm may be installed as `@anthropic-ai/claude-code@<version>`
when that package/version is verified. Match its runtime/base-image requirements; do not assume a
copy of a host binary runs in a different container architecture.

Provision supported authentication independently. Depending on the installed CLI and account, this
may be an API key or an OAuth token such as `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`. Inspect
local help/authentication guidance; do not assume credentials are inherited by child/container runs.
Do not mount the user's `.claude` configuration tree or store credentials in run artifacts.

## Optional skill-creator helpers

Discover helpers in the installed skill-creator distribution; none is required. Older
`aggregate_benchmark.py` implementations glob `eval-*/<config>/run-*`, subtract configurations in
alphabetical order, and emit placeholder model/repeat metadata. Check all of these before using one;
the builder's explicit comparison direction, null metrics, and configuration modes remain binding.
Keep any legacy helper output separate from the canonical benchmark contract.

Some `scripts.run_loop` versions plant command stubs under a nearby `.claude/commands/`. If using
such a helper, give it a disposable directory and inspect its supported arguments. Stub invocation
proposes a description; it does not measure discovery of the installed project skill. Confirm the
description through real development runs, and never use held-out task results to tune it.
