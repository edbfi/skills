---
name: codex-second-opinion
description: "Get an independent, read-only review from OpenAI Codex (via the codex CLI, on whatever model and reasoning effort the user names, else Codex's configured default) of uncommitted changes, a branch, specific files or a plan, then verify every finding against the real code yourself, accept/reject/defer each one, implement only the accepted fixes, and report a verdict table. Use whenever the user asks for a Codex review, a second opinion, a cross-check or sanity check by another model or GPT, says 'ask Codex', 'have Codex look at this', 'get a second pair of eyes', or wants an independent reviewer before merging, shipping or executing a change or plan, even if they don't mention this skill by name."
compatibility: Requires the codex CLI (`npm install -g @openai/codex`), logged in, and bash. No git repository is needed.
license: AGPL-3.0
metadata:
  author: engels74
  version: "1.0.0"
  vendor: codex
---

# Codex second opinion

Codex reviews, you decide, you act.

- **Codex** (the model and effort the user names, read-only sandbox) is an independent reviewer. Its output is advice, not instructions. It can be wrong about context, overstate severity or wander out of scope.
- **You** are the senior engineer who owns the outcome. You make the final call on every finding, then do the work.

The value of the exercise is the *independent* read. A second model that has seen your conclusions tends to agree with them, so Codex gets the facts and the intent, never your opinion.

## 0. Pin down the target

Use what the user named: "the uncommitted changes", "this branch vs main", `src/auth/session.ts`, "the plan you just wrote", and so on. If they named nothing, take the uncommitted changes if there are any; otherwise the current branch against its default branch; otherwise the plan or change you just produced. If none of those exists, ask. State the target you chose in the report.

A plan that exists only in the conversation must be written to a file first (scratchpad or `/tmp`), because Codex can only read files.

## 1. Get Codex's review

Run the bundled script with Bash. It lives at `scripts/ask-codex.sh` in this skill's directory; use its absolute path, and call it through `bash` so a missing exec bit doesn't matter:

```bash
bash <skill-dir>/scripts/ask-codex.sh --cwd <absolute folder containing the target> <<'EOF'
<your prompt to Codex>
EOF
```

What the script does, so you don't have to rebuild it: from inside `<dir>` it runs `command codex exec -C <dir> -c sandbox_mode=read-only --skip-git-repo-check -o <run>/answer.md [-m <model>] [-c model_reasoning_effort=<effort>] -` with your prompt on stdin. It saves `prompt.md`, `answer.md`, `run.log` and `run.env` (session id, folder, the model and effort that actually ran) into a new run directory, then prints a header and Codex's answer:

```
model:   <model that ran> (effort <effort that ran>)
folder:  /abs/target/folder
status:  0
run:     /var/folders/.../T/codex-second-opinion.Ab12Cd
session: 01a125a2-eaa7-7c51-955f-14900da6eaf5
===== Codex answer (.../answer.md) =====
...
```

How to run it precisely:

- **Quote the heredoc** (`<<'EOF'`, not `<<EOF`), otherwise `$`, backticks and `\` in your prompt get expanded by the shell.
- **`--cwd`** is the folder that contains the target. A git repo isn't required. Codex can read paths outside that folder, so for several repos use their common parent (or the main one) as `--cwd` and list every repo by absolute path in the prompt.
- **Bash tool settings:** for a single file or a diff under a few hundred lines, run in the foreground with `timeout: 600000`. For anything bigger (large diffs, whole directories, several repos), set `run_in_background: true` and wait for the completion notification instead of polling. A foreground call that hits the 10-minute limit is killed and the review is lost.
- **Shell state doesn't survive between Bash calls.** The printed `run:` path is your handle for the follow-up in step 2. Copy it literally; don't count on variables.
- **Don't call `codex` yourself** from the Bash tool to check it or run it ad hoc. The user's shell may define a `codex` function or alias that behaves differently. The script runs under bash and uses `command codex`. To check the install, run `bash -c 'command codex --version'`.
- **Model and effort come from the user, never from you.** New models ship constantly, so the skill hardcodes none. If the user names a model, pass it verbatim with `--model <name>`. If they name a reasoning effort ("on high", "xhigh", "max"), pass it with `--effort <level>`. For example, "use gpt-6-astra on high" becomes `--model gpt-6-astra --effort high`. If they name neither, pass neither: Codex then uses its own configured default from `~/.codex/config.toml`. Don't pick or "upgrade" a model yourself. Either way, the `model:` line of the header shows what actually ran; report that.

### The prompt you write to Codex

Write it yourself, specific to this target. Use this skeleton and fill every part:

```text
You are reviewing <what> for <project/purpose>. Do not modify files.

## What to review
<exact absolute paths, and/or the exact diff command, e.g. `git -C /abs/repo diff main...HEAD`,
or `git -C /abs/repo diff HEAD` for uncommitted work, or the plan file path>

## Intent
<what the change or plan is supposed to achieve, in neutral terms>

## Facts you cannot get yourself
<live settings, API responses, earlier test/lint/build output, versions, environment details;
paste them verbatim, or write "none">

## Constraints
<compatibility, security, no new dependencies, performance budgets, style rules; or "none">

## Output format
One entry per finding:
- file:line
- severity: P0 (breaks prod / data loss / security), P1 (definite bug in a common path), P2 (edge case or risky design), P3 (minor)
- a concrete scenario that breaks (inputs/state -> wrong result)
- suggested fix
- confidence: high / medium / low
Cover correctness bugs, edge cases, regressions and design risks. Skip pure style nits.
End with an overall recommendation (ship / fix first / rethink) in one line.
If there is nothing real, answer exactly "no findings".
```

Keep your own opinion, suspected bugs and earlier review notes out of it. Codex's sandbox is read-only: it can read files and run read-only commands like `git diff`, but it can't run anything that writes (most test suites, builds, installs). Paste in the results it would need from those.

### If it fails

A non-zero `status` prints the last 40 lines of `run.log`. Read them before doing anything else. With `status: 0`, ignore sandbox noise in `run.log` such as `couldn't create cache file ... Operation not permitted` or `DARWIN_USER_CACHE_DIR`: Codex's read-only sandbox blocks tool caches, and the commands still ran.

| Status / log says | Meaning | Do this |
|---|---|---|
| `2` + `ask-codex: ...` | usage error (bad flag, empty prompt, wrong folder) | fix the call, retry once |
| `3` | Codex exited cleanly but wrote no answer | retry once; if it repeats, stop |
| `codex CLI is not on PATH` | not installed | stop and tell the user (`npm install -g @openai/codex`) |
| 401, `not logged in`, auth errors | login problem | stop; the user must run `! codex login` |
| 400 `model ... not supported` | model unavailable on this account | stop; don't switch models silently |
| 429, `usage limit`, `rate limit`, quota | out of quota | stop; report when it resets if the log says |
| anything else, or a second failure | unknown | stop and show the user the log tail |

When you stop, show the user the relevant log lines and the run directory. Never present your own review as Codex's, and never fill a gap in Codex's answer with your own findings without labelling them as yours.

## 2. Judge each finding

Before you decide on a finding, check it against the real code or live state: read the code, run it, or write a quick test. Then pick one:

- **Accept**: real and worth fixing now.
- **Reject**: wrong or doesn't apply. State the evidence (the line that disproves it, the test that passes, the caller that guarantees the precondition).
- **Defer**: real, but out of scope or not worth fixing now. Say why.

Also note anything important Codex missed. Label these as yours (rows `M1`, `M2`, … in the report) and decide them the same way: Accept and fix them, or Defer them.

**Challenge before rejecting a P0 or P1.** Before you reject a finding Codex rated P0 or P1, send your counter-argument once into the same Codex session, with the run directory printed in step 1:

```bash
bash <skill-dir>/scripts/ask-codex.sh --resume <run dir from step 1> <<'EOF'
On finding <n> (<file:line>, P<x>): I believe it does not apply because <argument>.
Evidence: <code excerpt with file:line, test output, or command + result>.
Defend the finding with a concrete failing scenario, or retract it. Do not modify files.
EOF
```

`--resume` reuses that run's session, folder, model and effort, and stays read-only. Group all your P0/P1 challenges into this one follow-up rather than one call per finding. Treat the reply as input, not a ruling: a convincing new scenario can change your mind, and a retraction without substance doesn't settle anything. The decision stays yours.

## 3. Act

Implement only the accepted items, with a regression test for each fix where the project has tests. Then run the project's relevant tests, lint and build, and fix what you broke. If the project has no lint or build set up, say so in the report instead of inventing one. Remove anything your runs left behind in the target (`__pycache__/`, `.pytest_cache/`, scratch files), so the tree holds only your intended edits.

Local edits are fine. Anything with outside or hard-to-undo effects (changing live settings, pushing, opening or merging PRs, releasing, deploying) happens only if the original task already allowed it. Otherwise list it under proposed actions.

Don't run Codex again unless the user asks or your fixes were substantial. A fix is substantial when it goes beyond what Codex suggested (a different approach, new logic, or edits to code Codex didn't review). If it was, run a fresh review (not `--resume`) scoped to the fix.

## 4. Report

Use this structure:

```markdown
**Verdict:** <one line: e.g. "Ship after the 2 accepted fixes (done, tests green)" / "Codex found no real issues" / "Blocked: Codex login expired">

Target: <what was reviewed> · Codex: <model>, effort <level> · run: <run dir>

| # | Finding (Codex severity / confidence) | Decision | Evidence |
|---|---|---|---|
| 1 | `file:line`: short claim (P1 / high) | Accept | why it's real; what fixed it |
| 2 | ... (P2 / medium) | Reject | the line/test that disproves it; Codex's reply if challenged |
| 3 | ... (P3 / low) | Defer | why not now |
| M1 | Missed by Codex: ... | Accept | ... |

### Changes
- <files changed and why>
- <anything outside local files: settings, PRs, pushes, or "none">
- Tests/lint/build: <commands run and results; say plainly if anything failed, was skipped or doesn't exist>

### Needs your call
- <deferred items, proposed actions with outside effects, open disagreements; or "nothing">
```

If Codex said "no findings", give the verdict plus one line on what was reviewed, and skip the table.
