# edbfi/skills

Agent Skills for the open [Agent Skills](https://agentskills.io) ecosystem,
installable via the [`skills`](https://github.com/vercel-labs/skills) CLI.

## Install all skills

    bunx skills add edbfi/skills

## Install a single skill

    bunx skills add edbfi/skills --skill docendo-orchestrate-bricks

## Skills

| Vendor | Skill | Description |
|---|---|---|
| astro | [`starlight-docs`](astro/starlight-docs/SKILL.md) | Build, configure, and author Starlight (Astro-based) documentation sites. |
| augmentcode | [`codebase-retrieval`](augmentcode/codebase-retrieval/SKILL.md) | Semantic codebase search via Augment's context engine. |
| basedpyright | [`basedpyright-python-gate`](basedpyright/basedpyright-python-gate/SKILL.md) | Drive Python to 0 errors / 0 warnings under basedpyright `recommended` mode by fixing code, never by suppressing globally. |
| bevy | [`bevy`](bevy/bevy/SKILL.md) | Build, debug, test, and migrate Bevy games and apps with version-checked ECS, rendering, assets, UI, and platform guidance. |
| codex | [`codex-second-opinion`](codex/codex-second-opinion/SKILL.md) | Get an independent read-only Codex review via the codex CLI, verify each finding, fix only what is real and report a verdict table. |
| coding-guidelines | [`coding-guidelines-builder`](coding-guidelines/coding-guidelines-builder/SKILL.md) | Build version-verified coding-guidelines skills for a tech stack, written as the delta from what agents already know. |
| docendo | [`docendo-orchestrate-bricks`](docendo/docendo-orchestrate-bricks/SKILL.md) | Plan and operate Docendo calendar bricks with ego-browser, task-overview accounting, and configurable module profiles. |
| lowendtalk | [`let-vps-scout`](lowendtalk/let-vps-scout/SKILL.md) | Find and purchase-verify the cheapest European VPS from LowEndTalk offers with ego-browser, subagents and one archived HTML report. |
| pelican-eggs | [`panel-egg-roundtrip`](pelican-eggs/panel-egg-roundtrip/SKILL.md) | Round-trip Pelican and Pterodactyl eggs through temporary panel installations. |

## License

AGPL-3.0. See [LICENSE](LICENSE).
