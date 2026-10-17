---
name: coding-guidelines-builder
description: Research a tech stack (one language or many components - languages, runtimes, frameworks, libraries, databases, tools, with optional version constraints, language modes and minimum targets) from primary sources at its latest stable release, or the version line named, and produce a guidelines library - organised, sourced, example-verified Markdown packs of current best practices, recent changes and anti-patterns that AI coding agents read from any project. Use whenever the user wants coding guidelines, a coding standard, best practices, rules or reference docs for agents on a stack or language, or wants existing guideline packs refreshed or re-verified, even if they never say "guidelines library".
compatibility: Requires file and command access, primary-source research (web, MCP, browser or git), Python 3.11+ for the bundled scripts, and a toolchain for the stack (Docker or host). Parallel workers and an independent review context are used when available.
license: AGPL-3.0
metadata:
  author: engels74
  version: "2.0.0"
  vendor: coding-guidelines
---

# Coding Guidelines Builder

Given a tech stack, research every component from primary sources at its latest stable release (or
the version line named), and produce a guidelines library that AI coding agents consult while
writing or reviewing code on that stack. For each component and each seam between components it
covers idiomatic usage, what changed in recent releases, and anti-patterns with their modern
replacements, all sourced, dated and backed by examples that compile. Entry files stay short and
route; topic files are complete. Thoroughness and currency are the goal.

Model training data lags stable releases, so nothing in a pack comes from memory: every claim is
researched at the release being documented and cites its source.

The output is plain documentation, **never a skill**: no `SKILL.md`, no skill frontmatter, and
nothing written into a skill-discovery directory (`.agents/skills/`, `.claude/skills/`,
`.codex/skills/`). Agents use a pack because someone points them at it.

## Inputs

- **The stack**, in ordinary language or as a list: components, plus any version constraints,
  language modes (Swift 6 mode, Rust 2024 edition), targets (minimum OS, runtime or browser) and
  exclusions. Keep each exactly as written. A role the stack needs but does not name (formatter,
  test runner) is chosen by research.
- **Library root** (optional): where packs are written. Default `./guidelines/`. In a repository
  that already has a library (agent-rules keeps it in `guidelines/`), use that one.
- **Stack id** (optional): the name of the stack pack.
- **Refresh** (optional): `refresh: <pack path>` or `refresh: all`, optionally with `force`.

Do not interview beyond what blocks progress. Execution preferences (research tools, browser mode,
worker mechanism) are honored when given.

## Versions

Default to the latest stable release. `TypeScript 6` means the newest stable 6.x, `TypeScript
6.0.3` exactly that, plain `TypeScript` the newest stable overall. Prereleases only when named.
Compatibility narrowing, pack ids, LTS lines and the full rules are in
`references/pack-format.md` ("Version resolution"); `scripts/registry_versions.py` does the lookups.

## Output

```text
<library-root>/
  INDEX.md
  components/<id>/   README.md, changes.md, practices/<topic>.md, anti-patterns.md,
                     sources.md, pack.json, examples/
  stacks/<id>/       README.md, versions.md, decisions.md, integration/<seam>.md,
                     anti-patterns.md, sources.md, pack.json, examples/
```

`references/pack-format.md` is the normative format. Topics come from the coverage checklist for
each component's kind in `references/checklists/`.

## Phases

| Phase | Work | Read first |
|---|---|---|
| 0 Setup | Run folder and `manifest.md`; parse the request into components with kinds, constraints, modes and targets; pick the library root; preflight research tools, workers, an independent review context and toolchains | `references/workspace.md`, `references/runtime.md` |
| 1 Resolve | `registry_versions.py`; compatibility narrowing; pack ids; reuse lookup in the library; mark dependent stacks | `references/research.md` §1-2, `references/pack-format.md` |
| 2 Research | Per component, in parallel when possible: optional probe, primary-source facts, component outline | `references/research.md` §3-4 |
| 3 Write components | Each component pack against its checklist and outline, in `draft/` | `references/pack-format.md`, `references/writing-rules.md`, `references/checklists/<kind>.md` |
| 4 Seams | For stacks: list interacting pairs, research them, write `integration/` files and the stack example project | `references/research.md` §5 |
| 5 Assemble stack | Stack README, `versions.md`, `decisions.md`, anti-patterns, `pack.json` | `references/pack-format.md` |
| 6 Verify examples | Build, check and test every `examples/` on the pinned toolchain and targets; record `verification` | `references/toolchain.md` |
| 7 Validate | Scripts below, on every new or refreshed pack | this file |
| 8 Review | Rubric review per pack; fix; revalidate | `references/review.md` |
| 9 Deliver | Copy packs from `draft/` into the library, regenerate `INDEX.md`, clean up, report | this file |

Phases are sequential and checkpointed in `manifest.md`. Changed inputs invalidate dependent phases.
Every stack that references a component created or refreshed in this run is refreshed in the same
run, so stack and component versions always agree.

## Validation

Run from the run folder against each draft pack (`$BUILDER_DIR` is this skill's directory):

```bash
python3 "$BUILDER_DIR/scripts/verify_examples.py" draft/components/<id> --json
python3 "$BUILDER_DIR/scripts/packs.py" hash draft/components/<id>
python3 "$BUILDER_DIR/scripts/packs.py" check draft/components/<id> draft/stacks/<id>
python3 "$BUILDER_DIR/scripts/packs.py" sources draft/components/<id> draft/stacks/<id>
```

`packs.py check` resolves a stack's component packs relative to the stack's library, so assemble
drafts in the same `components/` and `stacks/` layout and check stacks after their components. After
delivery, `packs.py check --library <root>` validates the whole library and `packs.py index <root>`
regenerates `INDEX.md` (`--check` fails when it is stale, `--stale` lists packs past their
`refresh_after`). All checks must pass; fix the pack, never the check.

## Refresh

Re-research a pack when its resolved version changed, its `refresh_after` passed, `force` was
given, or it has verification limitations or open review items. Otherwise report it current.
Details in `references/workspace.md` ("Refresh").

## Delivery

1. Copy each validated pack from `draft/` to the library root, replacing the previous version of
   the same pack only; never touch other packs.
2. Run `packs.py index <root>` and `packs.py check --library <root>`.
3. Remove resources `manifest.md` marks as created by this run (containers, volumes, networks,
   clones). Keep the run folder for later refreshes.
4. Report: packs created, reused and refreshed, resolved versions and narrowings, verification
   limitations, review independence, and the path to each pack's `README.md`. To use a pack from
   another project, point the agent at that `README.md`.

## Optional harm check

When asked, `references/harm-check.md` compares a few tasks with and without a pack to catch
guidance that makes results worse. It informs fixes; it never deletes content.
