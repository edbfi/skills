# Waiting in T3 Code

Read this when T3 Code's `watch_pull_request` tool is available and you own the PR (not a
delegated child; see section 6). T3's watch is then the only waiter for the PR. Based on the
babysit-pr skill in [t3dotgg/tstack](https://github.com/t3dotgg/tstack).

## Arm the watch

1. `link_pull_request` the PR when you start on it. Linking twice is harmless.
2. Finish a full round on the checks and comments that already exist.
3. Call `watch_pull_request`. Only activity after the call wakes you, so run `pr-ops.sh status
   --since <cursor>` once more and handle anything that slipped in. Then end the turn without a
   message.

The watch persists across wakes. It ends when the PR merges or closes, when the thread settles or
is archived, after 8 failed reads in a row, when the user stops the thread, or on
`unwatch_pull_request`. Don't call it again every round. After a resume or compaction, if you
aren't sure it is still active, call it again.

## On each wake

A wake is news, not a merge decision. Start a round at section 1 step 1; readiness is always the
section 7 check, never the wake's text. A wake that needs nothing ends the turn silently.

The watch doesn't see everything:

- It reports conflicts but not `BEHIND`. Check `mergeStateStatus` yourself (section 5).
- It doesn't wake when a non-required check passes. If a wake leaves nothing to do except such a
  check still running on `head_sha` (a review bot that passes without posting when a push brings
  nothing new), wait for that one GitHub Actions run in the background with
  `gh run watch <run-id> --exit-status -i 30`, then do a round. The PR watch stays armed. This
  waits for one run already in flight, never the PR and never in a loop. A non-Actions check gets
  no such wait.

## Stop

- Before stopping for any reason except merged or closed (ready, blocked, a question for the user,
  not converging), call `unwatch_pull_request`. Otherwise the thread stays in the user's Working
  list instead of their inbox. Merge and close end the watch on their own.
- If the watch ends unexpectedly ("stopped watching, could not read it"), first check that reading
  still works: `gh auth status` and `pr-ops.sh status`. If GraphQL is spent
  (`gh api rate_limit --jq .resources.graphql` shows `remaining` near 0), wait for `reset` with one
  background command. Watch again only once reading works; otherwise report. Never re-watch in a
  tight loop.
- If T3 refuses to watch because the thread is settled or archived, stop and tell the user. Agents
  can't unsettle a thread.
