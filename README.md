<p align="center">
  <img src="assets/skills.svg" alt="skills logo" width="160" height="160">
</p>

<h1 align="center">skills</h1>

<p align="center"><strong>Reusable skills for coding agents and everyday workflows.</strong></p>

<p align="center">
  <a href="https://github.com/edbfi/skills/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--or--later-blue?style=flat" alt="License: AGPL-3.0-or-later (council subtree: MIT)" title="AGPL-3.0-or-later; tstack/council remains MIT (see License below)"></a>
</p>

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
| basedpyright | [`basedpyright-python-gate`](basedpyright/basedpyright-python-gate/SKILL.md) | Drive Python to 0 errors / 0 warnings under basedpyright `recommended` mode by fixing code, never by suppressing globally. |
| bevy | [`bevy`](bevy/bevy/SKILL.md) | Build, debug, test, and migrate Bevy games and apps with version-checked ECS, rendering, assets, UI, and platform guidance. |
| codex | [`codex-second-opinion`](codex/codex-second-opinion/SKILL.md) | Get an independent read-only Codex review via the codex CLI, verify each finding, fix only what is real and report a verdict table. |
| coding-guidelines | [`coding-guidelines-builder`](coding-guidelines/coding-guidelines-builder/SKILL.md) | Research a tech stack at its latest stable release and build a sourced, example-verified guidelines library that agents read from any project. |
| context7 | [`docs-scout`](context7/docs-scout/SKILL.md) | Search library docs and coding guidelines with the Context7 Search API (two keys balanced across their quota) and agent-browser web search, then read and cite the sources. |
| docendo | [`docendo-orchestrate-bricks`](docendo/docendo-orchestrate-bricks/SKILL.md) | Plan and operate Docendo calendar bricks with ego-browser, task-overview accounting, and configurable module profiles. |
| github | [`babysit-pr`](github/babysit-pr/SKILL.md) | Shepherd a PR through review bots and CI: verify every finding, fix what is real, answer each comment with a verdict and its commit. |
| lowendtalk | [`let-vps-scout`](lowendtalk/let-vps-scout/SKILL.md) | Find and purchase-verify the cheapest European VPS from LowEndTalk offers with ego-browser or agent-browser, subagents and one archived HTML report. |
| pelican-eggs | [`panel-egg-roundtrip`](pelican-eggs/panel-egg-roundtrip/SKILL.md) | Round-trip Pelican and Pterodactyl eggs through temporary panel installations. |
| revanced | [`revanced-device-test`](revanced/revanced-device-test/SKILL.md) | Test a ReVanced patches bundle the way users use it: on the test device, through the CLI and ReVanced Manager, then check each patch in the patched app. |
| seedream | [`seedream5-prompt-enhance`](seedream/seedream5-prompt-enhance/SKILL.md) | Turn a rough image idea, edit or reference brief into one Seedream 5.x prompt (pro, flash, lite and later), following ByteDance's official ModelArk guides. |
| tstack | [`council`](tstack/council/SKILL.md) | Ask three flagship models from different providers to review or advise, with scores and rounds in the PR description (adapted from t3dotgg/tstack). |
| wan | [`wan3-prompt-enhance`](wan/wan3-prompt-enhance/SKILL.md) | Organize a Wan 3.0 video request and its Image/Video/Audio references into a faithful five-section prompt (English translation of Alibaba Cloud's official skill, merged with the Wan 3.0 prompt guide). |

## License

Except for separately licensed third-party material, original code and documentation
in this repository are licensed under the GNU Affero General Public License,
version 3 or (at your option) any later version (SPDX: `AGPL-3.0-or-later`).
See [LICENSE](LICENSE) for the full license text.

`tstack/council` is adapted from [t3dotgg/tstack](https://github.com/t3dotgg/tstack)
and stays MIT; see [its LICENSE](tstack/council/LICENSE). Bundled Archivo fonts
retain the [SIL Open Font License 1.1](lowendtalk/let-vps-scout/assets/fonts/OFL.txt).
Other upstream material retains its own license and notices.
