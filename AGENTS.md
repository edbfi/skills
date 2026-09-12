# AGENTS.md

This file provides guidance to AI coding agents when working with code in this
repository.

## What this repo is

A content-only collection of Agent Skills published for the [Agent Skills](https://agentskills.io)
ecosystem and installed with the [`skills`](https://github.com/vercel-labs/skills) CLI. Every
skill file is Markdown or YAML. There is no application build or runtime test
suite. [CI.md](CI.md) documents read-only prek checks and the repository contract
validator for skill metadata, index membership and reference paths. Shared CI
and Renovate keep automation dependencies consistent.

## Layout contract

```
<vendor>/<skill-name>/SKILL.md          # required entry point
<vendor>/<skill-name>/references/*.md   # optional deep-dive docs
<vendor>/<skill-name>/agents/*.yaml     # optional per-client interface metadata
```

- **The skill directory name must equal the frontmatter `name`.** The `skills` CLI discovers
  skills by that pairing plus the exact `SKILL.md` filename.
- **The parent directory is the vendor namespace** and must match `metadata.vendor` where that
  field is present (`astro/starlight-docs` → `vendor: astro`).
- **`<vendor>/<skill-name>` is a public install path.** `README.md` documents single-skill
  installs as `npx skills add https://github.com/edbfi/skills/tree/main/augmentcode/codebase-retrieval`.
  Renaming or moving a skill directory breaks that URL for existing users — treat it as a
  breaking change, not a refactor.

## Adding or changing a skill

1. Create `<vendor>/<skill-name>/SKILL.md` with the frontmatter below.
2. Keep `SKILL.md` a router, not an encyclopedia. `astro/starlight-docs/SKILL.md` is 102 lines
   and delegates ~2,950 lines to ten task-mapped references. When content grows, add a
   `references/*.md` and a routing line rather than expanding `SKILL.md`.
3. Link references with a path relative to the skill directory (`references/foo.md`). Reference
   files carry **no** frontmatter — they start directly with an `# H1`.
4. Add or update the row in the `## Skills` table in `README.md`. That table is the repository's
   only index; a skill added without it is effectively undiscoverable.
5. Commit with Conventional Commits, scoped to the vendor directory where one applies:
   `feat(pelican-eggs): add panel egg round-trip skill`, `chore(renovate): standardize policy`.

## SKILL.md frontmatter

| Field | Status | Notes |
|---|---|---|
| `name` | required | Must equal the containing directory name. |
| `description` | required | Single physical line. See gotchas below. |
| `compatibility` | when applicable | Free-text prerequisite, e.g. an MCP tool that must be configured in the agent. |
| `license` | expected | Exactly `AGPL-3.0`. |
| `metadata.author` / `.version` / `.vendor` | expected | `engels74`, a quoted semver string, and the vendor directory name. |

`license` and `metadata` are present on `starlight-docs` and `codebase-retrieval` but absent on
`panel-egg-roundtrip`; the repo does not state which is canonical. Include both on new skills,
and leave `panel-egg-roundtrip` alone rather than normalizing it as a drive-by change.

## Gotchas

- **`description:` must stay on one physical line.** The three existing skills run 455–1006
  characters unwrapped. Wrapping it, or reformatting it into a YAML block scalar, changes how
  clients parse and match the skill. Edit the line in place; do not "tidy" the frontmatter.
- **Write `description` as a trigger list, not a summary.** The established pattern: one
  sentence of what the skill does, then explicit "Use this skill whenever…" clauses naming
  concrete user phrasings, file paths, and package names, then a negative clause saying when
  *not* to use it. A short generic description will not route correctly.
- **The license identifier is `AGPL-3.0`, never `AGPL-3.0-or-later`.** `LICENSE` is GNU AGPL v3
  with no "or later" clause. Keep `SKILL.md` frontmatter, `README.md`, and `LICENSE` in
  agreement.
- **`agents/openai.yaml` is optional and per-skill.** Only `panel-egg-roundtrip` has one; it
  declares `interface.display_name`, `.short_description`, and `.default_prompt`. Do not add it
  to other skills speculatively, and keep the `$name` reference inside `default_prompt` equal to
  the skill's `name`.

## Validation before committing

Run `SKIP=no-commit-to-branch prek run --all-files`. To inspect the entry points:

```bash
git ls-files '*/*/SKILL.md'   # each path's directory name must match its frontmatter `name`
```

Then confirm: every `references/…` link in a `SKILL.md` resolves relative to that skill's
directory; the `README.md` table row exists and its link target is real; `license` and
`metadata.vendor` agree with the directory path.

## Reference files

- `README.md` — install commands and the skill index. Read before adding, renaming, or removing
  a skill.
- `astro/starlight-docs/SKILL.md` — canonical multi-reference skill: routing table, progressive
  disclosure, negative trigger clause. Read when authoring a skill that needs `references/`.
- `augmentcode/codebase-retrieval/SKILL.md` — canonical single-file skill with a
  `compatibility` prerequisite and a tool-selection decision table. Read when authoring a skill
  with no references.
- `pelican-eggs/panel-egg-roundtrip/references/roundtrip-workflow.md` — 11-stage operational
  runbook (resource ledger, Colima setup, both panel flows, validation, cleanup audit). Read
  only when editing the Pelican/Pterodactyl round-trip procedure.
