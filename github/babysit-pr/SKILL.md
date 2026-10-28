---
name: babysit-pr
description: "Monitor a pull request through AI review bots and CI until it is ready: verify every bot finding, fix what is real, and answer each one with a VALID / INVALID / OUT OF SCOPE reply, reaction and resolved thread. Use when the user asks to monitor, watch, babysit, shepherd or land a PR, or to handle review-bot comments."
license: AGPL-3.0
compatibility: Requires git, bash, jq and an authenticated GitHub CLI (gh 2.96+ validated) with write access to the pull request's repository.
metadata:
  author: engels74
  version: "2.0.0"
  vendor: github
---

# Babysit PR

Many repos have AI review bots. They're helpful, even if they are not always right. You own the
PR: verify each finding against the code, fix what is real, and answer every bot comment with a
verdict and its evidence, so a later reader sees what each finding was, whether it held up and
which commit fixed it.

Review reads and writes go through `scripts/pr-ops.sh` in this skill's directory (`bash
<skill-dir>/scripts/pr-ops.sh <command>`). Every write asserts what GitHub stored, so exit 0 means
it happened. Exit 3 means your answer is already there: finish what it still lacks (`react` and
`resolve` are safe to repeat) and don't force it. `--repo owner/name --pr N` default to the
current checkout and branch. Check details and logs (`gh pr checks <n> --json
name,bucket,link`, `gh run view`), reruns, branch updates and the merge use `gh` directly.

## Waiting

Never write your own watcher, polling loop, or `sleep` loop. Use one watcher per PR:
`watch_pull_request` in T3 Code, `pr-ops.sh wait` everywhere else. Never run both on the same PR.
Every watcher on a GitHub account shares one rate limit.

### In T3 Code: `watch_pull_request`

This applies whenever `watch_pull_request` is available, even as a deferred tool. Link the PR
with `link_pull_request` and handle the existing checks and comments first (a round, see
Reviews). If the merge gate passes or babysitting ends, finish there (Base branch and merging)
without watching. Otherwise call `watch_pull_request`, run `status --since <cursor>` once more and
handle anything that slipped in. If the gate now passes or babysitting ends, finish there;
otherwise end your turn. T3 Code wakes you with a message when a check fails, the required checks
pass, someone comments or reviews, or the branch conflicts. The watch persists across wakes; after
a resume or compaction, call it again if you aren't sure it is active.

- **Only the thread that owns the PR watches it.** If you are a delegated child task (a reviewer,
  any `delegate_task` child), never call `watch_pull_request`, never wait and never merge. Finish
  the round and end with `PR <url>, head <head_sha>, checks and reviews <state>`. The parent owns the
  PR.
- **A wake is news, not a merge decision.** Start a round and check the merge gate yourself.
- **Blind spots.** The watch reports conflicts but not BEHIND, so check `mergeStateStatus`
  yourself. It doesn't wake when a non-required check passes. Bots usually finish long before CI,
  but if the required checks have passed and the only thing left on `head_sha` is an active bot's
  own run, don't wait for it any other way: run `status` once more, and if it is still running,
  hand off as "Stopped: <bot>'s run still going" with its link.
- **Unwatch when you hand off.** A watched thread stays in Working and out of the user's inbox.
  When babysitting ends without a merge or close (ready, blocked, or asking the user a question),
  call `unwatch_pull_request` first, even if you go on to other work. A merge or close ends the
  watch on its own.
- **"Stopped watching, could not read it"** usually means GitHub's rate limit is used up. Run
  `gh api rate_limit --jq .resources.graphql` before you watch again. If `remaining` is near 0,
  wait for `reset` with one background command, then watch again. Never watch again in a tight
  loop. If T3 refuses because the thread is settled or archived, tell the user.

### Everywhere else: `pr-ops.sh wait`

```bash
bash <skill-dir>/scripts/pr-ops.sh wait --since <cursor> [--timeout 1800]
```

It prints `{"reason": ...}` and returns on `new-activity`, `checks-finished`, `head-changed`,
`merge-state` (the branch became BEHIND or DIRTY), `pr-MERGED` or `pr-CLOSED`, and exits 124 on
`timeout`.

In Claude Code, run it in the background (`run_in_background: true`) so its exit wakes you. With
scheduled wake-ups, schedule the next round instead. Otherwise run it in the foreground with
`--timeout` under your tool's time limit, and loop. Start it again after every round, including
rounds that needed nothing, and after a resume. After a timeout, run `status` before waiting
again. After about two hours without any change, stop and report what you are waiting on.

With either watcher: when an event needs no action, end your turn without a message (in a
foreground loop, just keep looping). Never post or say "still waiting".

## GitHub rate limits

`gh pr create`, `gh pr view`, `gh pr checks` and `pr-ops.sh status`, `wait` and `resolve` use
GraphQL. The other `pr-ops.sh` commands use it only to fill in a missing `--repo` or `--pr`, so
pass both when GraphQL is spent. The REST limit is separate and usually still has room. Use
`gh api repos/<owner>/<repo>/pulls/<n>` to read a PR, and
`gh api repos/<owner>/<repo>/commits/<sha>/check-runs` for checks. Thread state lives only in
GraphQL, so wait for `reset` before you resolve.

## Reviews

Before the first round, read the repository's rules (`AGENTS.md`, `CLAUDE.md`, `.agents/rules/`,
`CONTRIBUTING.md`, linter config) and the bots' rule files (`.coderabbit.yaml`,
`.macroscope/check-run-agents/*.md`, `.github/copilot-instructions.md`, a bot workflow's prompt).
They decide how commits must look, and the bots' findings cite them. Work in a clean checkout of
the PR's head; use a separate worktree if the user has unrelated changes. The PR's goal (the
user's request, else its title and description) is the fence for every fix.

### A round

1. **Snapshot.** `pr-ops.sh status [--since <cursor>]` prints JSON with the PR (`head_sha`,
   `mergeStateStatus`, ...), head checks, reviewers and what needs you: `pending_threads`,
   `followups` (replies after you resolved), `feedback` (review bodies and top-level comments you
   haven't acked) and `unfinished_threads` (your reply is there but the thread isn't resolved:
   only `react` and `resolve`). `awaiting_humans` are for the human to resolve.
2. **Base.** If the branch needs updating (Base branch and merging), do that before pushing fixes.
3. **CI.** Handle failing checks on `head_sha` (below).
4. **Judge** every pending thread, followup and feedback item. Investigate first; write nothing
   yet.
5. **Fix** what is `VALID`. Run the repository's checks and hooks, commit following its rules
   (one focused commit per unrelated fix, with a real message such as
   `fix(parser): reject empty --since values`), and push.
6. **Answer.** If you pushed, wait until `git rev-parse HEAD` equals `head_sha` in a fresh
   `status`, so replies cite pushed commits.
7. **Cursor.** Pass step 1's `cursor` (not a later one) as `--since` next round, once everything
   it showed is answered; feedback older than the cursor stays hidden.

Only checks on `head_sha` count. A thread on an older commit (`isOutdated: true`) still counts
until you check whether it applies at HEAD.

### Judging a finding

Verify every bot finding against the source at HEAD before changing code: read the code and its
callers, run the test, or write a quick reproduction. Ask two questions in order:

1. **Is the claim real at HEAD?** Real means a concrete failing scenario you confirmed, a broken
   rule the repository documents, or a reachable security, data-loss or concurrency issue (for
   these, if you can't disprove it, treat it as real). Otherwise it is `INVALID`. If it was real
   and a later commit in this PR fixed it, it is `VALID` with that commit.
2. **Is fixing it within the PR's goal?** If yes, `VALID`: fix it. If no, `OUT OF SCOPE`.

| Verdict | Means | Reaction |
|---|---|---|
| `VALID` | Real and in scope. Fixed as suggested or another way. | 👍 |
| `INVALID` | Wrong, or a preference with nothing behind it. | 👎 |
| `OUT OF SCOPE` | Real, but fixing it would widen the PR. | 😕 |

Some bots act on reactions (a "fix the 👍 findings" button), so never 👍 a finding this PR won't
fix.

Keep the PR at the size the user's goal needs. Review loops tend to grow a PR one cheap-looking
fix at a time. Fix real bugs in the intended case and correct nitpicks on lines the PR touches.
Answer the rest as `OUT OF SCOPE` (list those as follow-ups) or `INVALID`: unneeded tests, guards
for edge cases that do not matter, extra integration or compatibility, small performance costs,
pre-existing problems and refactors. Prefer the fix that deletes or narrows code. A real, in-scope
problem that is expensive to fix is the user's call, and so is opening an issue.

If a bot repeats a finding you answered or argues back without new evidence, answer once more
with the same verdict and a link to your earlier reply, then resolve. With new evidence, judge
again; a flipped verdict is fine. Acknowledgements ("Addressed in `<sha>`", "Thanks", "LGTM")
need no reply.

### Answering bot comments

For each inline thread or followup that needs an answer:

```bash
bash <skill-dir>/scripts/pr-ops.sh reply --comment <latest_comment_id> <<'EOF'
VALID. <why it is real, one or two sentences>. Fixed in <full sha>.
EOF
bash <skill-dir>/scripts/pr-ops.sh react --comment <latest_comment_id> --verdict VALID
bash <skill-dir>/scripts/pr-ops.sh resolve <latest_comment_id>
```

`--verdict` takes `VALID`, `INVALID` or `'OUT OF SCOPE'`. `reply` finds the thread's root itself,
and `resolve` takes several IDs, so you can batch resolves at the end of the round. Quote the
heredoc so backticks and `$` reach GitHub literally.

Start each reply with the verdict and a full stop, then one to three sentences of checkable
evidence: a pushed full SHA for `VALID`, a `path:line`, test, caller or doc for `INVALID`, the
PR's goal for `OUT OF SCOPE`. No thanks, no hedging, and no @-mentions of bots (many treat a
mention as a command).

```text
INVALID. `limit` can't be 0 here: `parse_args()` rejects values below 1 (`cli.py:88`) and `test_limit_must_be_positive` covers it.
OUT OF SCOPE. `retry()` never caps its backoff, but that predates this PR, whose goal is the token refresh.
```

Findings in review bodies or top-level comments (nitpick sections, "outside diff range" notes)
get **one** top-level comment per source, with a verdict per finding. Pass the item's `ack_id`
from `feedback` (`pullrequestreview-<id>` or `issuecomment-<id>`):

```bash
bash <skill-dir>/scripts/pr-ops.sh comment --ack <ack_id> <<'EOF'
Re: <url of the review or comment>

1. "Unused import in `sync.py`": VALID. Removed in <sha>.
2. "Prefer a dataclass for `Config`": INVALID. The module keeps plain dicts for TOML round-tripping (`config.py:12-30`).
EOF
```

Findings a review body only summarises are answered in their threads. Pure summaries,
walkthroughs and "No new issues found" need no answer. Screenshots and videos help when a fix
changes something visible and you have a way to upload them. `references/github-operations.md`
documents each call and what it asserts, for when one fails.

Human reviewers get no verdict labels, reactions or resolves. Implement clear in-scope requests
and reply in plain prose with what changed. Bring disagreements, questions about intent and
anything out of scope to the user, and leave their threads for them to resolve.

### Reviewers

Learn how each reviewer runs from this PR and the repository rather than assuming a bot.

- **Bots review every push by themselves.** One that runs as a check is pending until its check
  on `head_sha` finishes. A passed check with nothing posted after the push means it found
  nothing (Pullfrog does this). One run can cover several quick pushes: if its log shows the
  reviewed range ending at `head_sha`, it reviewed the head.
- **Wait only for active bots:** one that reviewed the previous head or whose check runs on this
  head. CodeRabbit is advisory: treat its findings like any other, but never wait for it and
  never hold a merge for it.
- **Retrigger only as a last resort:** long after a bot's usual delay, and only with a trigger the
  repository documents or this PR's history shows working:
  `pr-ops.sh retrigger --trigger '<exact text>'`. Never post a trigger from memory.

### CI failures

Read the failing check's evidence first (`gh run view <run-id> --log-failed` for Actions). A
test, lint, type, build or policy failure caused by the code, commits or PR metadata is a
repository failure: reproduce it, fix it and push. A lost runner, network or registry timeout,
5xx or rate limit is an infrastructure flake: rerun once (`gh run rerun <run-id> --failed`). If it
fails the same way again, stop rerunning: fix it, or report it if it is outside the repository.
Never rerun a repository failure hoping for green, and don't touch CI config or skip tests unless
that is the PR's goal.

## Base branch and merging

Keep an eye on changes to the base branch and rebase when the PR is DIRTY, when it is BEHIND and
branch protection requires an up-to-date branch, or when new base commits touch this PR's files
(`git log HEAD..<base-remote>/<base> -- <files>`). Otherwise leave it: every rebase restarts CI
and reviews. Pick remotes by URL (`<base-remote>` matches `base_repo`, `<head-remote>` matches
`head_repo`; in a fork, `origin` is usually the fork) and pin the lease to the head you rebased:

```bash
git fetch <base-remote> <base> && git fetch <head-remote> <headRefName>
git merge-base --is-ancestor <head_sha> HEAD   # stop if the local branch lacks the PR head
git rebase <base-remote>/<base>                # resolve conflicts, rerun the checks
git push --force-with-lease=refs/heads/<headRefName>:<head_sha> <head-remote> HEAD:refs/heads/<headRefName>
```

If the lease is rejected, someone pushed: start the round over. If the repository merges the base
into branches instead or forbids force-pushes, follow that (`gh pr update-branch <n>`). If an
overlapping PR makes this one obsolete, stop monitoring, report it to the user, and ask before
closing the PR unless closure was explicitly authorized.

The **merge gate** passes when, on `head_sha`: nothing is failing or pending (an advisory bot's
check aside); every active bot has
`reviewed_head: true` or a passed check covering the head with nothing posted since;
`pending_threads`, `unfinished_threads` and `followups` need nothing more; every feedback item is
answered or needs no answer; the PR is not a draft; and `mergeStateStatus` is `CLEAN` (or
`HAS_HOOKS`).

Merge only when the user explicitly requested it; otherwise report that the PR is ready. Right
before a merge, run `git fetch <base-remote> <base>` and `status --since <cursor>` again. Never
merge when the head moved, when it is BEHIND or DIRTY, or when base commits that landed after the
last green run touch this PR's files: rebase, push, and wait for green again. Merge with the
method the repository allows, pinned to the head you checked and never with `--admin`:
`gh pr merge <n> --squash|--merge|--rebase --match-head-commit <head_sha>`.

### When babysitting ends

Babysitting this PR ends when it merges or closes, is ready without a merge request, is
superseded, waits on the user, or stops converging (a check fails the same way after your fix, or
bots keep repeating answered findings). That ends this PR, not necessarily your turn. If it
reached what the user asked for and the request includes more work, note the outcome in one line
with any follow-ups (`Merged #12 as 4c1e9b0; follow-ups: retry backoff (OUT OF SCOPE)`) and
continue. Otherwise, or when you hand back at the end, report:

```markdown
**Status:** Merged | Ready to merge | Done, blocked by <reason> | Superseded by #N | Stopped: <why>

PR: <url> · head `<short sha>` · rounds: <n> · checks: <pass/fail/pending>

| Source | Finding | Verdict | Evidence / commit |
|---|---|---|---|
| <bot> `path:line` | short claim | VALID | `<short sha>` |

Needs your call: <deferred items, open questions, proposed outward actions; or "nothing">
```

"Done, blocked" means the reviews and checks are finished but GitHub still won't merge: a
required approval, a required check that never started, a human thread, or a draft. Never report
it as ready.
