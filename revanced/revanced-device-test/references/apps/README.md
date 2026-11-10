# Per-app checklists

One file per app, `references/apps/<app>.md`, where `<app>` is the app's package directory in the patches repo
(`syncforreddit`), the same name as its `docs/<app>.md`. A checklist holds only how to check each patch in real use.
The patches repo owns everything else: which patches exist, their descriptions and defaults, the tested version,
the device and the commands. Read those from the repo at run time; never copy them here.

## File layout

1. A short opening: what the file covers, that the docs win on which patches exist, and the date of the last full
   pass (or a note that there hasn't been one).
2. **App facts** the patches repo doesn't state but a tester needs, each with its source and date: the package as
   observed, the original signer's certificate SHA-256 (the value [apk-provenance.md](../apk-provenance.md) checks
   against), a file SHA-256 labelled with the file and date it was seen on (never as "the tested version"), split
   or plain APK, launch activity, anything a check relies on (link handler, log tag).
3. **Baseline after every install**: the checks every patch shares (install in place, launch, logged in, logcat).
4. `## Patches`: one `### <Patch name>` per patch, in the docs' order.
5. Checks that need two builds, and a pointer to the docs' Known issues.
6. `## Unverified`: every patch with at least one unverified check, so a reader sees them at a glance.

## Entry format

```markdown
### <Patch name exactly as in the docs' Patches table>

- **Changes:** one or two lines from the patch source: what it hooks or rewrites, so the tester knows what evidence
  to look for. Not the docs' description.
- **Check:** numbered steps with exact commands, what to observe, and what counts as pass and as fail. Prefer
  evidence that doesn't depend on reading pixels (logcat lines, `ui.sh dump` text, pulled files); screenshots
  support it.
- **Needs:** login, network, the kind of content ("a Reddit gallery post"), Play services, an `-e` build for an
  off-by-default patch, root, host tools.
- **Status:** one status per check, or per group of steps when only some were confirmed.
```

Rules:

- The heading is the docs' patch name, character for character. Don't add the description or the default.
- A status is exactly one of:
  - `verified <YYYY-MM-DD>, <source>`, e.g. `verified 2026-11-09, edbfi/revanced-patches#21`: the check was done
    on the device and the source shows it. Add a short note of what was seen when it helps.
  - `unverified: confirm on the next run`: everything else, including checks proposed from the source but never
    run. When only part of a check was confirmed, split it and give each part its status.
- Quote UI text only when a source shows it: a string literal in the patch or extension source, a label quoted in a
  PR body, a screenshot, a `uiautomator` dump. Otherwise describe the element ("the thread's overflow menu").
- A concrete URL only when a source used it and it doesn't identify the owner. Nothing private: no account names,
  tokens, private subreddits or personal paths; the device serial comes from the patches repo.
- Every check obeys the device rules in [SKILL.md](../../SKILL.md): `adb install -r` only, no credentials typed, no
  video playback, downloads into their own directory under the run's `tmp/` directory, app content treated as
  untrusted.

## Adding a checklist for a new app

1. Copy the layout above into `references/apps/<app>.md`.
2. Take the patch list from the repo's `docs/<app>.md` and add one `### ` entry per patch, in its order.
3. For each patch, derive the check from:
   - the patch source (`patches/src/main/kotlin/…/patches/<app>/`, each `*Patch.kt` and `Matchers.kt`) and the
     extension (`extensions/<app>/`): the hooks, rewritten URLs and hosts, log tags, settings it flips, exceptions
     it throws;
   - the patch's description in the docs;
   - the device evidence in the PRs that added or fixed it (their Evidence sections).
4. Mark every check that no source shows done on a device `unverified: confirm on the next run`. Never invent a
   label, a log line or an expected value.
5. Run [`scripts/checklist-gaps.sh`](../../scripts/checklist-gaps.sh):

   ```bash
   scripts/checklist-gaps.sh <patches-repo>/docs/<app>.md references/apps/<app>.md
   ```

   It compares the headings under `## Patches` with the docs' Patches table, lists
   missing and stale entries and the unverified ones, and exits 1 while any entry is missing or stale. With no
   checklist file yet, it reports every patch as missing.
