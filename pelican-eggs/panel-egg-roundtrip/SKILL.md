---
name: panel-egg-roundtrip
description: Round-trip Pelican PLCN_v3 YAML and Pterodactyl PTDL_v2 JSON egg files through temporary panel installations using Docker/Colima and agent-browser, then replace manual working files with genuine panel exports and remove every temporary resource. Use when an egg repository requires panel-generated exports, when reviewing or updating Pelican/Pterodactyl eggs, or when manual JSON/YAML edits must be imported and re-exported before submission.
---

# Panel Egg Round-Trip

Produce authentic panel exports without installing persistent Pelican or Pterodactyl environments. Treat manually edited egg files only as import sources; the final repository files must be the downloaded panel exports.

## Required workflow

1. Inspect repository instructions and working-tree state.
2. Load the `agent-browser` skill, then run `agent-browser skills get core --full` before browser automation.
3. Read [references/roundtrip-workflow.md](references/roundtrip-workflow.md).
4. Prepare the desired egg changes and validate the import sources.
5. Create an isolated Colima profile and temporary Compose workspace.
6. Round-trip the Pelican YAML through Pelican Panel.
7. Round-trip the Pterodactyl JSON through Pterodactyl Panel.
8. Replace the repository files with the downloaded exports.
9. Validate semantic invariants, generated markers, scripts, and diff.
10. Remove all containers, volumes, networks, images, browser sessions, credentials, temporary files, Docker context, and the Colima profile.

Do not stop after import. A successful result requires downloaded exports in the repository and a completed cleanup audit.

## Safety contract

- Use a unique named Colima profile. Never run destructive cleanup against the user's default Docker context.
- Give both Compose projects unique names and record every created path/resource.
- Keep Compose files, passwords, browser downloads, and panel data outside the target repository.
- Generate temporary passwords into mode-`0600` files. Never print them or place literal values in commands, logs, screenshots, or commits.
- Replace Pterodactyl's `/srv/pterodactyl/...` bind mounts with task-scoped named volumes. Never write panel data into host `/srv`.
- Never manually edit an egg after its final panel export. If a correction is needed, edit the working import source and repeat the import/export.
- Preserve unrelated containers, images, volumes, networks, Colima profiles, and Docker contexts.
- On failure, continue to cleanup unless evidence needed for diagnosis would be destroyed; capture that evidence first.

## Import-source checks

Before starting panels:

- Confirm the Pelican file declares `meta.version: PLCN_v3`.
- Confirm the Pterodactyl file declares `meta.version: PTDL_v2`.
- Parse JSON and YAML with available local tooling.
- Extract both installation scripts and run `bash -n` on each.
- Compare shared semantics: name, author, description, images, denylist, startup, process configuration, installation script, and variables.
- Save the pre-round-trip Git diff for later comparison.

## Panel export rules

### Pelican

- Import the YAML from **Admin → Eggs → Import → File**.
- Upload through the actual `input[type=file]`; styled upload buttons may not hold the file input.
- Wait for the filename/upload completion before submitting.
- Export with **Export → As .yaml**.
- Pelican's Livewire download can ignore the requested filename and save a UUID-like file. Identify the newly downloaded file by timestamp/content, validate it as PLCN_v3 YAML, then rename it.

### Pterodactyl

- Import the JSON from **Admin → Nests → Import Egg**.
- Select a temporary nest after inspecting the actual `<select>` options; do not guess an option value.
- Export from the imported egg's **Configuration → Export** link.
- Validate the download as PTDL_v2 JSON before replacing the repository file.

## Final validation

Require all of the following:

- Both final files contain their panel-generated warning/comment and a fresh `exported_at` value.
- Format versions remain PLCN_v3 and PTDL_v2.
- Requested changes survived both round-trips.
- Installation scripts pass `bash -n`.
- Cross-panel shared semantics remain equivalent, allowing panel-specific schema differences and harmless serialization order/newline changes.
- `git diff --check` passes and the diff contains no temporary paths, credentials, panel URLs, or unrelated formatting churn.
- The repository contains no Compose files, databases, browser state, or downloaded intermediate artifacts.

## Completion report

Report:

- Final exported file paths.
- Panel versions/images used.
- Import/export and validation evidence.
- Any expected panel serialization changes.
- Cleanup audit results.
- Known limitations, such as an install URL that intentionally becomes available only after merge.
