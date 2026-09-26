# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Content-only repo of Agent Skills published via `npx skills add edbfi/skills`. There is no build, app, or test suite; the only automated check is a content contract plus prek hygiene hooks.

## Commands

- Content contract (fast, run after any skill or README edit): `python3 scripts/check-content.py`
- All local hooks: `SKIP=no-commit-to-branch prek run --all-files`
- CI then runs `git diff --exit-code HEAD`, so hooks must leave tracked files unchanged.

## Layout invariants (enforced by `scripts/check-content.py`)

- A skill is exactly `<vendor>/<skill>/SKILL.md`, two levels deep. A `SKILL.md` at any other depth is not validated or indexed.
- The directory path is the public install path (`https://github.com/edbfi/skills/tree/main/<vendor>/<skill>`). Don't rename or move a published skill or change its `description`; add a new skill instead.
- Frontmatter rules the checker parses line by line (`^key: value`):
  - `name` must equal the skill directory name.
  - `description` must be one line. A `|` or `>` block scalar fails; write a single long line.
  - `license`, if present, must be `AGPL-3.0`.
  - `metadata.vendor` (indented two spaces), if present, must equal the vendor directory.
- `README.md` must contain a link `(<vendor>/<skill>/SKILL.md)` for every skill; its Skills table is the index.
- Every `references/*.md` path mentioned in a `SKILL.md` body must exist. Other relative paths (e.g. `agents/`) are not checked, so verify them by hand.

## Adding a skill

1. Create `<vendor>/<skill>/SKILL.md` with frontmatter, e.g. from `astro/starlight-docs/SKILL.md`:
   ```yaml
   ---
   name: starlight-docs
   description: Build, configure, customize, and author content for documentation sites using Starlight, ...
   license: AGPL-3.0
   metadata:
     author: engels74
     version: "1.0.0"
     vendor: astro
   ---
   ```
   `license`/`metadata` are optional; `pelican-eggs/panel-egg-roundtrip/SKILL.md` omits them.
2. Keep `SKILL.md` short (existing ones are ~100 lines) and put detail in `<vendor>/<skill>/references/*.md`, routed from the body.
3. Optional Codex UI metadata goes in `<vendor>/<skill>/agents/openai.yaml` (see `pelican-eggs/panel-egg-roundtrip/agents/openai.yaml`).
4. Add a row to the Skills table in `README.md`.
5. Run `python3 scripts/check-content.py`.

## Git and CI

- With `prek install` active, the `no-commit-to-branch` hook blocks commits on `main`; work on a branch and open a PR.
- Commit-message hook (`prek install --hook-type commit-msg`) requires Conventional Commits; include matching author sign-offs (`git commit -s`).
