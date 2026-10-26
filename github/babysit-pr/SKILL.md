---
name: babysit-pr
description: "Shepherd a GitHub pull request through AI review bots and CI until it is green on the latest commit: watch or poll the PR, verify every bot finding against the real code, fix what is real, answer each inline bot comment with a VALID / INVALID / OUT OF SCOPE verdict reply (with the fixing commit), react and resolve the thread, answer summary-only nitpicks in one top-level comment, fix CI failures, rerun infrastructure flakes and rebase when needed. Provider-agnostic: works with any review bot (Pullfrog, CodeRabbit, Copilot, Gemini and others). Use whenever the user asks to monitor, watch, babysit, shepherd or land a PR, to get a PR green, or to handle, triage or reply to review-bot comments, even if they don't name this skill."
license: AGPL-3.0
compatibility: Requires git, bash, jq and an authenticated GitHub CLI (gh 2.96+ validated) with write access to the pull request's repository.
metadata:
  author: engels74
  version: "1.2.0"
  vendor: github
---

# Babysit PR

Bots review, you decide, you act, and the PR keeps the record.

AI review bots are useful and often wrong. They miss context outside the diff, assume other library
versions, invent APIs and pad reviews with taste. You are the engineer who owns the PR: verify each
finding against the code, fix what is real, and answer every bot comment with a short verdict and
its evidence. A later reader of the PR should be able to see what each finding was, whether it held
up and which commit fixed it, without re-investigating.

All GitHub reads and writes go through `scripts/pr-ops.sh` in this skill's directory. Call it by
absolute path through bash (`bash <skill-dir>/scripts/pr-ops.sh <command> ...`). It implements
[references/github-operations.md](references/github-operations.md), and every write asserts what
GitHub stored, so exit 0 means it happened. `--repo owner/name --pr N` default to the current
checkout and branch; pass them explicitly when you are anywhere else. Exit 3 means the script
refused to post a duplicate because your answer is already there. Don't force it; finish whatever
that answer still lacks (`react` and `resolve` are safe to repeat).

## 0. Set up

1. **Rules.** Read the target repository's agent and contribution rules (`AGENTS.md`, `CLAUDE.md`,
   `.agents/rules/*.md`, `CONTRIBUTING.md`, linter and formatter config). They decide what counts
   as a convention violation and how commits must look (Conventional Commits, DCO sign-off with
   `git commit -s`, and so on). Read the review bots' own rule files too (`.coderabbit.yaml`,
   `.macroscope/check-run-agents/*.md`, `.github/copilot-instructions.md`, a bot workflow's
   prompt), because their findings cite them.
2. **The PR.** Use the number or URL the user gave, else the current branch's PR. Check out its head
   branch in a clean working tree. If the user has unrelated uncommitted work, use a separate
   worktree rather than mixing it in.
3. **The goal.** Take the scope from the user's original request, else the PR title and
   description. This is the fence for every judgement below. Fixes stay inside it, even when a bot
   suggests otherwise.
4. **Authority.** Babysitting includes pushing fixes to the PR branch. Merging needs an explicit
   request from the user. Closing the PR, force-pushing anything other than a rebase of this branch,
   opening issues and anything else outward-facing need the user's go-ahead unless they already
   gave it.
5. **First snapshot.** Run `status` and learn how each reviewer in `reviewers` runs (below).

### How reviewers run

Assume no particular bot. Learn each reviewer's behaviour from this PR and the repository: its
earlier reviews, its check runs, its configuration file or workflow.

- **Bots review every push by themselves.** Some run as a CI check and post their review only after
  that check finishes (Pullfrog runs with CI, then posts a review saying whether anything needs
  action). Treat such a reviewer as pending until its check on `head_sha` has finished.
- **A passed check can be the whole review.** Bots that review incrementally often stay silent
  when a push brings nothing new: the check on `head_sha` passes, but no review is posted and
  `reviewed_head` stays `false` (Pullfrog does this). If the bot's check on `head_sha` passed and
  it posted nothing after the push, it found nothing to say; read the check's log to be sure when
  it is cheap. Don't wait for a review that won't come.
- **One run can cover several pushes.** Pushes seconds apart often get one bot run, and its check
  attaches to the earlier commit. If the run's log shows its reviewed range ending at `head_sha`
  (Pullfrog logs `pr-<n>-<from>-<to>-incremental.diff`), it reviewed the head; don't wait for
  another.
- **Expected reviewers are the active ones.** `reviewers` lists everyone who ever reviewed or
  commented inline, including bots since removed and humans. Wait only for bots that are still
  active: one that reviewed the previous head, or one whose check runs on this head. A bot that
  skipped the last pushes is not coming back; mention it in the report instead of waiting for it.
- **Retrigger only as a last resort**: when a reviewer has clearly not reviewed the latest push
  long after its usual delay, *and* the repository documents an exact trigger comment or this PR's
  history shows one that worked. Then use `pr-ops.sh retrigger --trigger '<exact text>'`, which
  reuses a trigger that is still active. Never post a trigger from memory; bot commands change and
  old ones go stale.
- **Don't @-mention a bot in a reply.** Many bots treat a mention as a command and answer again.
  Replying inside a bot's thread can itself start a conversation; its answer shows up as a pending
  thread or followup, and you judge it like any other comment.
- **Summary-only findings are feedback too** (section 3). **Pure summaries need no answer**: a
  recap of the change, a walkthrough, "No new issues found".

## 1. The loop

Repeat until a stop condition in section 7 holds.

1. **Snapshot.** `pr-ops.sh status [--since <cursor>]` prints JSON:
   - `pr`: state, `isDraft`, `head_sha`, `head_repo` and `base_repo` (they differ for a fork),
     `mergeStateStatus` (`CLEAN`, `BEHIND`, `DIRTY` = conflicts, `BLOCKED`, `UNSTABLE`, ...).
   - `checks`: `counts`, `failing` (with `required`), `pending`, for the head commit only.
     `required_reported` lists only required checks that have reported; one that never started
     shows up as `mergeStateStatus: BLOCKED`, not here.
   - `reviewers`: everyone non-self who reviewed or commented inline, with `bot`, `reviewed_head`
     and `last_review_commit`.
   - `pending_threads`: unresolved inline threads whose latest comment is not yours.
   - `unfinished_threads`: unresolved bot threads that end with your reply, meaning an earlier
     round stopped between `reply` and `resolve`. Finish them with `react` and `resolve`; don't
     reply again.
   - `awaiting_humans`: unresolved human threads that end with your reply. They're the reviewer's
     to resolve.
   - `followups`: threads you resolved where someone replied after you.
   - `feedback`: review bodies and top-level comments you haven't answered with `comment --ack`,
     plus any edited after your answer. Bodies are complete; read all of one before judging it.
   - `cursor`: GitHub's clock when the snapshot started. Pass it back as `--since` next round so
     feedback and followups you've already seen stay hidden. Threads don't need it; their state
     lives on GitHub.
   Checks from older commits are history; only `head_sha` counts. A thread on an older commit
   (`isOutdated: true`) still counts until you check whether it still applies at HEAD.
2. **CI.** Handle `checks.failing` (section 4).
3. **Judge** every pending thread, followup and feedback item (section 2). Investigate first and
   write nothing yet.
4. **Fix** the items you judged `VALID`. Run the repository's own checks locally (its
   test suite, linters, pre-commit/prek hooks), commit following the repository's rules, and push.
   Give unrelated fixes separate commits so each reply can cite a focused commit, and write real
   commit messages (`fix(parser): reject empty --since values`), not "address review comments".
5. **Answer** (section 3). Replies cite pushed commits, so answer after the push lands: `git
   rev-parse HEAD` must equal `head_sha` in a fresh `status`.
6. **Reviewers.** Let them review the push on their own; retrigger only under the last-resort
   rule in section 0.
7. **Base branch.** Rebase when needed (section 5).
8. **Wait** (section 6), then go back to step 1.

## 2. Judge each finding

A verdict needs evidence either way. Check the claim against the code at **HEAD** (not the commit
the bot saw): read the code and its callers, run the test, or write a quick reproduction. "Looks
fine to me" is not a reason, and neither is "the bot said so".

There are three verdicts. Pick one by answering two questions, in this order:

1. **Is the claim real at HEAD?** If the evidence disproves it, or nothing real stands behind it
   (no defect, no documented rule, no requirement), the verdict is `INVALID`.
2. **Is fixing it within this PR's goal?** If yes, it is `VALID`: fix it. If no, it is
   `OUT OF SCOPE`.

| Verdict | Means | Reaction |
|---|---|---|
| `VALID` | Real and in scope. Fixed, as the bot suggested or another way (say how in the reply). | 👍 |
| `INVALID` | Wrong, or a preference with nothing behind it. | 👎 |
| `OUT OF SCOPE` | Real, but fixing it would widen the PR beyond its goal. | 😕 |

The reaction records the outcome: 👍 agreed and fixed, 👎 wrong, 😕 real but not fixed here. Some
bots act on reactions (a "fix the 👍 findings" button, for one), so a finding this PR won't fix
must never get a 👍.

The reason in the reply must be something a reader can check: a commit for `VALID`, a
`path:line`, test, caller or doc for `INVALID`, and the PR's goal for `OUT OF SCOPE`. If you can't
name one, you haven't finished judging.

**Real** means at least one of these holds:

- You can state a concrete failing scenario (inputs or state, then the wrong result) and you
  confirmed it by reading the reachable path or running it.
- It breaks a rule the repository documents (rules files, linter config, contribution guide), or
  the PR's own stated goal.
- It is a security, data-loss or concurrency issue on a reachable path. For these the bar to
  dismiss is higher: if you can't disprove it, treat it as real or ask the user.

**Common reasons a bot is wrong** (each is an `INVALID` when you can cite the evidence):

- The guard exists outside the diff: a caller validates, the type rules it out, a test pins it.
- It assumes a different version of a library, language or API than the lockfile pins, or an API,
  flag or option that doesn't exist.
- It misreads the diff (old side for new side), or the code it describes never behaved that way.
  (If the problem was real when the bot looked and a later commit in this PR fixed it, that is
  `VALID` with that commit.)
- The scenario isn't reachable: validated input, private function with known callers, impossible
  state.
- It contradicts the repository's documented conventions or its formatter.

**Scope and nitpicks.** A correct nitpick on lines this PR touches is `VALID`: fix it. A
suggestion that is only taste (no rule or defect behind it), or that contradicts the repository's
conventions, is `INVALID`. Pre-existing problems in code the PR doesn't change, refactors and
feature ideas are `OUT OF SCOPE`, however good, because the user decides scope. A real, in-scope
problem that is expensive to fix is none of these: it is the user's call, so list it under "Needs
your call".

**Keep the PR its size.** Review loops grow a PR one cheap fix at a time. Requests for extra tests,
guards, compatibility layers or micro-optimisations go through the same two questions: an
unreachable scenario is `INVALID`; a defect in the intended case is `VALID`; anything beyond the
intended case that no repository rule requires is `OUT OF SCOPE`, even on lines this PR touches.
The report's `OUT OF SCOPE` rows are the follow-up list. When you fix, prefer the fix that deletes
or narrows code.

**Repeats and rebuttals.** If a bot repeats a finding you already answered, or argues back without
new evidence, answer once more with the same verdict and a link to your earlier reply, then
resolve. Don't argue a third time. If it brings new evidence, judge again; a flipped verdict is
fine, so say so plainly. If you still can't decide after investigating, don't guess: list the item
under "Needs your call" in the report and leave the thread unresolved.

**Acknowledgements need nothing.** A bot reply like "Addressed in `<sha>`", "Thanks" or "LGTM" in a
followup gets no reply.

**Humans are not bots.** Comments from human reviewers don't get verdict labels, reactions or
resolution from you. Implement clear, in-scope requests and reply in plain prose saying what changed
and where. Bring disagreements, questions about intent and anything out of scope to the user rather
than disputing a person on the user's behalf. Leave resolving their threads to them.

## 3. Answer

### Inline threads

For each pending thread or followup that needs an answer, in this order:

```bash
bash <skill-dir>/scripts/pr-ops.sh reply --comment <latest_comment_id> <<'EOF'
VALID. <why it is real, one or two sentences>. Fixed in <full sha>.
EOF
bash <skill-dir>/scripts/pr-ops.sh react --comment <latest_comment_id> --verdict VALID
bash <skill-dir>/scripts/pr-ops.sh resolve <latest_comment_id>
```

`--verdict` takes `VALID`, `INVALID` or `'OUT OF SCOPE'` (quoted). `reply` finds the thread's
root itself. Quote the heredoc (`<<'EOF'`) so backticks and `$` reach
GitHub literally. `resolve` takes several IDs at once, so you can batch the resolves at the end of
the round.

**Reply template.** The first word is the verdict label followed by a full stop. Then come one to
three sentences with concrete evidence: `path:line`, the test name, the caller, the doc. Use a full
commit SHA (GitHub renders it as a short link) and never a SHA you haven't pushed.

```text
VALID. <why it is real>. Fixed in <sha>.
VALID. <why it is real>. Fixed differently in <sha>: <what you did instead and why>.
INVALID. <why the claim is wrong, with checkable evidence>.
OUT OF SCOPE. <why it is real>, but this PR's goal is <goal>. <Tracked in #N.>
```

Examples:

```text
VALID. `since` is compared against the local clock, so a skewed machine skips new comments. Fixed in 4c1e9b0d27a35f8e6b2d1c0a9f8e7d6c5b4a3f21.

INVALID. `limit` can't be 0 here: `parse_args()` rejects values below 1 (`cli.py:88`) and `test_limit_must_be_positive` covers it.

OUT OF SCOPE. `retry()` never caps its backoff, but that predates this PR, whose goal is the token refresh.
```

No thanks, no praise, no @-mentions of bots (section 0), and no hedging. For
`OUT OF SCOPE`, write "Tracked in #N" only when an issue exists; opening one is outward-facing, so it
needs the user's go-ahead.

### Feedback without an inline thread

Review bodies and top-level comments sometimes carry findings of their own: nitpick sections,
"outside diff range" notes, a bot's whole review when it posts nothing inline. Answer each source
with **one** top-level comment that lists a verdict per finding in the same template, quoting each
finding in a few words so readers can match them:

```bash
bash <skill-dir>/scripts/pr-ops.sh comment --ack pullrequestreview-<id> <<'EOF'
Re: <url of the review or comment>

1. "Unused import in `sync.py`": VALID. Removed in <sha>.
2. "Prefer a dataclass for `Config`": INVALID. The module deliberately keeps plain dicts for TOML round-tripping (`config.py:12-30`).
EOF
```

There's no thread to resolve and no reaction (a list can mix verdicts). Inline findings that a
review body merely summarises are answered in their threads, not again here. Feedback that has
nothing to judge (summaries, walkthroughs, "No new issues found") gets no answer; the cursor
retires it.

### Screenshots and recordings

When a fix changes something visible, a screenshot or short recording in the reply or the PR
description is the strongest evidence. The GitHub API can't upload images, so use a file-upload
skill or tool if one is installed; otherwise describe what you verified and how.

## 4. CI failures

Only checks on `head_sha` matter. For each failing check, read its evidence first. When the
check's `link` points to a GitHub Actions run (`/actions/runs/<run-id>/...`), use `gh run view
<run-id> --log-failed`. Any other link is an external CI service or GitHub App: read what that
link exposes, and if you can't read or rerun it, say so in the report rather than guessing. Then
decide:

- **Repository failure**: a test, lint, type check, build or policy check fails because of the
  code, the commits or the PR metadata (title format, sign-off). Reproduce it locally when you can,
  fix it, and push. Treat it like a `VALID` finding without a thread.
- **Infrastructure flake**: a runner lost or out of disk, network or registry timeouts, 5xx or rate
  limits from GitHub or a package registry, a job cancelled by a timeout with no failing step of its
  own, or a known flaky test that passes locally. Rerun once: `gh run rerun <run-id> --failed` for
  Actions, or the provider's documented retry for anything else.
  If the same check fails the same way again, it isn't a flake: treat it as a repository failure
  or, if it truly is outside the repository, report it to the user.

Don't rerun a repository failure hoping it goes green, and don't touch CI config or skip tests to
get green unless that is the PR's goal.

## 5. Base branch

Rebase onto the base branch when `mergeStateStatus` is `DIRTY` (conflicts), when it is `BEHIND`
and branch protection requires an up-to-date branch, or when the base gained changes this PR
interacts with (`git log HEAD..<base-remote>/<base> -- <files this PR touches>`). Otherwise leave it:
every rebase restarts CI and bot reviews.

Pick remotes by repository, not by name: `<base-remote>` is the remote whose URL is `base_repo`,
and `<head-remote>` the one whose URL is `head_repo` (`git remote -v`). In a fork checkout,
`origin` is usually the fork. Pin the lease to the exact head you rebased, so a commit someone else
pushed in the meantime makes the push fail instead of being overwritten:

```bash
git fetch <base-remote> <base> && git fetch <head-remote> <headRefName>
git merge-base --is-ancestor <head_sha> HEAD   # local branch must contain the PR head; stop if not
git rebase <base-remote>/<base>
# resolve conflicts, rerun the local checks
git push --force-with-lease=refs/heads/<headRefName>:<head_sha> <head-remote> HEAD:refs/heads/<headRefName>
```

If the lease is rejected, someone pushed: run `status` again and start the round over.

Rebase between rounds, not while bots are mid-review. SHAs quoted in earlier replies stay reachable
through the PR's history, so leave old replies as they are. If the repository merges the base into
branches instead of rebasing (merge commits in history, contribution rules), follow that, for
example with `gh pr update-branch`.

**Overlap.** If another PR or a commit on the base already achieves this PR's goal, stop
babysitting, report it with links and ask before closing anything (unless the user already
authorised closing).

## 6. Wait without noise

Prefer T3 Code. Whenever `watch_pull_request` is available, T3's PR watch is the only waiter for
the PR: never also run `pr-ops.sh wait`, a sleep loop or any other watcher. Every waiter on the
account shares one GitHub rate limit.

While waiting, post nothing: no status updates, no "still watching" comments, no re-pinging bots.
A wake that needs no action gets no message either.

**Delegated child** (a `delegate_task` child or any subagent of the thread that owns the PR): never
watch, wait or merge. Finish the round and return the PR URL, `head_sha` and the pending checks and
reviews to the parent, which owns the loop.

### In T3 Code

1. **Link** the PR with `link_pull_request` when you start on it (linking twice is harmless).
2. **Arm.** After a full round, call `watch_pull_request`. Only activity after the call wakes you,
   so run `status --since <cursor>` once more and handle anything that slipped in. Then end the turn
   without a message.
3. **It persists** across wakes until the PR merges or closes, the thread settles or is archived,
   8 reads fail in a row, the user stops the thread, or you call `unwatch_pull_request`. Don't call
   it again every round; after a resume or compaction, if you aren't sure it's active, call it
   again.
4. **A wake is news, not a merge decision.** Start a round at section 1 step 1. Readiness is always
   the section 7 check, never the wake's text.
5. **Blind spots.** The watch reports conflicts but not `BEHIND`, so check `mergeStateStatus`
   yourself (section 5). It doesn't wake when a non-required check passes: if a wake leaves nothing
   to do except such a check still running on `head_sha`, wait for that one GitHub Actions run in
   the background with `gh run watch <run-id> --exit-status -i 30`, then do a round. The PR watch
   stays armed; this waits for one run already in flight, never the PR and never in a loop. A
   check that isn't a GitHub Actions run gets no such wait.
6. **Hand-off.** Before stopping for any reason except merged or closed (ready, blocked, a question
   for the user, not converging), call `unwatch_pull_request`, so the thread returns to the user's
   inbox instead of staying in Working. Merge and close end the watch on their own.
7. **Watch ended unexpectedly** ("stopped watching, could not read it"): check that reading still
   works (`gh auth status`, `pr-ops.sh status`). If GraphQL is spent
   (`gh api rate_limit --jq .resources.graphql` shows `remaining` near 0), wait for `reset` with one
   background command. Watch again only once reading works, never in a tight loop; otherwise report.
8. **Settled or archived thread:** if T3 refuses to watch for that reason, stop and tell the user.
   Agents can't unsettle a thread.

### Without T3 Code

In Codex CLI, plain Claude Code or any other harness, block on `pr-ops.sh wait` between rounds.
Read [references/waiting-without-t3.md](references/waiting-without-t3.md) for its reasons and how to
run it in your harness. After about two hours without any change, stop and report what you are
waiting on.

## 7. Stop

Stop and report when one of these holds:

- **Ready**: on `head_sha`, nothing is failing or pending; every active bot (section 0) has
  `reviewed_head: true` or a passed check on `head_sha` with nothing posted since;
  `pending_threads`, `unfinished_threads` and `followups` need nothing more;
  every feedback item has been answered or needs no answer; the PR is not a draft; and
  `mergeStateStatus` is `CLEAN` (or `HAS_HOOKS`). Merge only if the user explicitly asked for it,
  using the merge method the repository allows and pinned to the head you checked:
  `gh pr merge <n> --squash|--merge|--rebase --match-head-commit <head_sha>`, never `--admin`.
  Right before merging, `git fetch <base-remote> <base>` (section 5) and run `status` again; if the
  head moved, the state is no longer `CLEAN` or `HAS_HOOKS`, or section 5's overlap check finds new
  base commits touching this PR's files, rebase, push and loop instead. Without a merge request,
  report that the PR is ready. In T3 Code, unwatch before reporting any stop other than merged or
  closed.
- **Done but blocked**: the bots and checks are finished, but GitHub still won't allow the merge
  (`BLOCKED`: a required approval, a required check that never started, `awaiting_humans`; or a
  draft). Report it as "review and CI done, blocked by <reason>", never as ready.
- **Merged or closed** by someone else.
- **Superseded** by an overlapping PR or commit (section 5).
- **Not converging**: after three rounds the bots only produce new low-value nitpicks, a check
  fails the same way after your fix, or the same disagreement keeps coming back.
- **Blocked** on the user: a decision outside your authority, a human reviewer's question, or an
  item you couldn't judge.

Report in this shape:

```markdown
**Status:** Ready to merge | Merged | Blocked: <why> | Superseded by #N | Stopped: <why>

PR: <url> · head `<short sha>` · rounds: <n> · checks: <pass/fail/pending counts>

| Source | Finding | Verdict | Evidence / commit |
|---|---|---|---|
| <bot> `path:line` | short claim | VALID | `<short sha>` |
| <bot> review body | short claim | OUT OF SCOPE | reason |
| CI `checks` | ruff F401 | fixed | `<short sha>` |

### Needs your call
- <deferred items, undecidable findings, human questions, proposed outward actions; or "nothing">
```
