# Waiting without T3 Code

Read this only when `watch_pull_request` isn't available (Codex CLI, plain Claude Code, other
harnesses) and you own the PR. In T3 Code, follow section 6 of SKILL.md instead.

Between rounds, block on `wait`. It returns when something actually changed:

```bash
bash <skill-dir>/scripts/pr-ops.sh wait --since <cursor> --timeout 1800
```

It prints `{"reason": ...}` for `new-activity`, `checks-finished`, `head-changed`, `merge-state`
(the branch became `BEHIND` or `DIRTY`; see section 5), `pr-MERGED` or `pr-CLOSED`, and exits 124
with `timeout` when nothing happened.

Pick the mechanism your harness offers:

- A harness that notifies you when a background command exits (Claude Code's Bash tool with
  `run_in_background: true`, for instance): run `wait` in the background, and go back to section 1
  step 1 when it finishes.
- A harness with scheduled wake-ups or a loop command: schedule the next round instead.
- Otherwise: run `wait` in the foreground with `--timeout` under your tool's time limit, and loop.

A wake that needs no action gets no message, but re-arm `wait` before you end the turn, since
silence is not stopping; in a foreground harness, just keep looping. When `wait` times out, run
`status` before waiting again, because a check can finish between a snapshot and the start of
`wait`.
