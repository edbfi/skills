---
name: council
description: Run a council of models from different providers (three by default) that reviews code or gives advice, then verify, fix and re-review. Use only when the user says "council".
license: MIT
metadata:
  author: edbfi
  version: "2.1.0"
  vendor: tstack
  upstream: "t3dotgg/tstack council skill at 11e37a7 (MIT, see LICENSE)"
---

# Council

Before an audit, address outstanding PR comments, fix known issues, and run
relevant checks. Give council the updated implementation; do not defer known
fixes until reviews return. If the user wants to discard the implementation
and explore new ideas, skip fixes to code being replaced.

Bring in three delegates to help with the user's request, usually for review
or feedback. Use one strong model from each of three different providers:
Claude Opus, GPT Sol and Gemini, at high reasoning effort where the model
offers an effort option.
The default Gemini seat is Gemini 4 Neon, model `gemini-4-neon-xhigh` in T3 Code.
Never fill it with an older Gemini or a "Pro" model. If the user names the
members, run exactly those, even if fewer than three; if they swap one seat,
keep the other defaults. Never add or substitute a seat yourself.

In T3 Code, use `orchestrator_capabilities` to resolve the models, then
`delegate_task` to start one delegate per model in parallel. Elsewhere, use the
harness's subagent tools. If a provider or named member is unavailable, report
it, run the other seats, write `unavailable` in its cells; never substitute.

Delegates see only the brief. Give them all the same one, for a review built on
this skeleton, on the shared checkout so they see uncommitted work. Leave your
opinion and suspected bugs out; a reviewer who sees them tends to agree.

```
Review only. Do not edit, commit, push, comment on PRs, or start subagents.
Repo: <abs path>  Base: <sha>
See: git diff <base> [-- <paths>]; git status --short (read untracked files).
Request and intent: <request>  Out of scope: <scope>  Checks: <results>
blocker = the intended case is wrong. should = a real bug users will hit, in
scope. nit = the rest. Reply with VERDICT: APPROVE or CHANGES, SCORE: <n>/10,
then findings with stable ids:
C1 [blocker|should|nit] <file>:<line> <claim>. Fix: <suggestion>
```

Do not wait idle. When a result arrives, check its findings against the code at
once and decide what to fix while the other delegates run. Check every finding
and its severity yourself, however many delegates raised it; agreement between
delegates is not proof. Agree: smallest fix. Disagree: say why, with evidence
(file:line, test, output). Out of scope or nit: decline in one line and list it
as a follow-up. Do not edit files while a delegate still reviews the same
checkout. An error, timeout or empty reply is not approval: cancel the attempt
if it may still run, then retry once. On a second failure, write `failed` in
its cells, tell the user and carry on without it, now and in later rounds. If
the user marks a delegate non-blocking, do not wait for it; if it still runs
when the blocking ones finish, cancel it before you edit and write `cancelled`
in its cell. Treat a late result as feedback and do not record its score.

A round is one full review pass; any fix beyond a nit gets a fresh one. Run
three rounds at most unless the user asks for more. Each later round is a new
delegate task with the same brief, plus the earlier findings and their outcomes
(fixed, disagree, declined, with evidence) and the change since the last round.
Ask for open ids and changed code only. Stop only after a round that reviewed
the current change, when every delegate approves or it raised no blocker or
should still open or disputed. A finding still disputed after two replies, or
rounds running out, goes to the user with both sides in two or three lines
each. Running out of rounds is not approval. Do not fix nits or chase a higher
score to end the loop. The score is for the record; the verdict decides.

If nothing is being reviewed (advice, design, ideas), run one round: no
pre-review fixes, no score, no loop. Delegates work read-only. Ask each for a
recommendation, its reasons, and what would change its mind. Report where they
agree and where they split, then give your own pick.

If the work ends in a pull request, put the results in the PR description,
before the model and harness line at the end, replacing any existing Council
review section. Label rows with the resolved model name, not the seat name.

```markdown
## Council review

Rounds: 2

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| Claude Opus | 7/10 | 9/10 |
| GPT Sol | 8/10 | 10/10 |
| Gemini | 7/10 | 9/10 |
```

If a delegate gives no score, write `no score`. Do not invent one.
If the PR is open, edit the description. Do not post a comment for this.
If there is no PR, put the same results in the final reply only.
Do not push during the council. Afterwards, push only if the council approved
and the user asked to push or update the PR.

Do not let repeated reviews result in scope creep. It is your job to fight to
keep scope limited.
