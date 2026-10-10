# Layout of the generated skill

```
<stack-slug>-guidelines/
├── SKILL.md                  # loaded whenever the skill triggers; routing and the delta, under budget
├── references/
│   ├── <component>.md        # one per component or tightly coupled pair; loaded on demand
│   ├── integration.md        # seams between components
│   ├── anti-patterns.md      # wrong / why / right / grep
│   └── versions.md           # release lines, modes, floors, conflicts, research date
├── assets/                   # lint/format/type-check configs and manifests to copy into projects
├── scripts/
│   └── check.sh              # build + lint + format check + tests, the same way evals grade
├── examples/                 # the verified project the code blocks come from (optional to ship)
└── PROVENANCE.md             # evidence table and sources; never referenced from loaded files
```

The skill is read in three layers: the description (always in context), `SKILL.md` (when the skill
triggers), and references (when `SKILL.md` sends the agent there). Content is placed by how often
an agent on an ordinary task needs it, not by how important it feels.

## SKILL.md

Budget: aim under 2,000 tokens, hard ceiling 3,000 (`$BUILDER_DIR/scripts/token_budget.py` reports
both).
Prefer short routing plus the verified delta; these budgets are ceilings, not targets.

Contents, in order, with these exact ATX headings (`check_provenance.py` keys its `structure` tag
to them and does not see setext underlines):

1. **Frontmatter.** `name` and a discriminating `description` (below).
2. **Thesis.** Prose directly under the title, no heading. One or two paragraphs: the stack's
   current posture, what to optimize for, and the two or three biggest ways an agent writes
   wrong-but-plausible code here, usually by importing habits from an adjacent ecosystem. This is
   the only place for framing prose.
3. **`## Decisions`.** The tools in use and the one-line reason for each non-obvious choice, the
   language mode, the minimum target. A short table if there are more than four.
4. **`## Top mistakes`.** The highest-frequency, highest-severity rows from `mistakes.md` and the
   contradicted probe rows, one line each: the wrong form, the right form, the reason. Six to ten
   lines at most; fewer when the evidence warrants fewer.
5. **`## Check`.** `scripts/check.sh` and the instruction to run it before finishing a task. One
   sentence on why: it is the same check the stack's CI and these guidelines are graded by.
6. **`## Routing`.** Which reference to read for which kind of work, keyed by what the agent is
   doing, not by component name alone:

   | When the task involves | Read |
   |---|---|
   | routes, handlers, extractors, middleware | `references/axum.md` |
   | queries, migrations, transactions, connection pools | `references/sqlx.md` |
   | anything async, spawning, cancellation, shutdown | `references/tokio.md` |
   | wiring the above together, app state, startup | `references/integration.md` |
   | checking code you did not write | `references/anti-patterns.md` |
   | a version question | `references/versions.md` |

Nothing else. No tutorial, no architecture overview, no restated basics.

## References

One file per component or tightly coupled pair, plus `integration.md`, `anti-patterns.md`, and
`versions.md`. Budget: aim under 4,000 tokens per file, ceiling 6,000; a file approaching the
ceiling is split by concern, and any file over 300 lines starts with a table of contents.

A reference file holds, for its component: the mistakes and contradicted beliefs that need more
than a line, each with its verified example; the configuration blocks; the decision tables where a
real choice exists. Headings are the implementation concerns an agent searches for while writing
(routing, extractors, error responses; queries, transactions, pooling; spawning, cancellation,
shutdown), not a universal skeleton.

Depth goes where the model goes wrong. A component with two baseline mistakes gets a short file; a
component with eight, several at seams, gets the long one. A component with no mistakes and no
cutoff-relevant facts gets no file, and its decisions live in `SKILL.md`.

## assets/ and scripts/

Ship what every run otherwise reinvents. If three baseline transcripts each wrote a linter config, the
skill ships the config in `assets/` and `SKILL.md` says to copy it. `scripts/check.sh` is the run's
`tasks/check.sh`, copied unchanged: the build, lint, format-check, and test sequence, taking the
project directory as its argument, so an agent runs one command and the evals grade with the same one.

## examples/

Shipping the example project is optional and off by default; the code blocks already carry the
verified content and the project adds size. Ship it when the stack's setup is intricate enough that
an agent benefits from a known-good project to diff against. Either way, `PROVENANCE.md` records
the toolchain versions the examples were verified with.

## PROVENANCE.md

```md
# Provenance

Model under test: <id>. Research date: <date>. Toolchain: <image tag @ digest or host versions>.

## Evidence

| file | section | evidence | reference |
|---|---|---|---|
| SKILL.md | Decisions | structure | layout |
| SKILL.md | Top mistakes | baseline | m-01, m-02, m-04 |
| SKILL.md | Check | structure | layout |
| SKILL.md | Routing | structure | layout |
| references/axum.md | Path parameters | probe | axum-02, axum-04 |
| references/sqlx.md | Pool configuration | decision | facts sqlx-07 |

## Sources

<the contents of research/sources.md>
```

`check_provenance.py` structurally requires a row with a nonempty reference for every ATX H2 and H3
in `SKILL.md` and `references/`, accepts `structure` only for the four fixed `SKILL.md` sections and
a `Contents` list, and requires a non-empty grep column for each anti-pattern row. Manually audit
evidence support as described in content-rules.md; include cited excerpts under an Evidence records
section. An anti-pattern table may have no data rows if the baseline/probe found none, but its header
and separator are still required. The file is never linked from loaded files.

## The description

The description is the trigger. Claude under-uses skills, so the description names the stack, the
kinds of tasks (writing, extending, reviewing, fixing, setting up), and says to use the skill for any
coding task on this stack even when the user does not name a framework. Phase 4 optimizes it
against near-miss negatives: tasks on an adjacent stack, questions about the stack that involve no
code, and projects that use only one of the stack's components outside this combination. Keep the
description under about 1,000 characters; it is in context for every conversation.

## What a stack skill is not

Not a `CLAUDE.md`. A project's `CLAUDE.md` holds that project's conventions and commands; the skill
holds what is true of the stack. If the user wants the guidelines applied unconditionally in one
repository, tell them to reference the skill from the project's `CLAUDE.md` rather than copying
content into it.
