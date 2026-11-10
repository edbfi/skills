# ReVanced Manager on the test device

How to get a verified ReVanced Manager onto the device, set it up, load a patches bundle, patch with it, and get
the output back out, all over adb. It also covers what Manager does with several bundles at once, which decides
whether a bundle patches at all. Read it before the Manager part of the workflow in SKILL.md, and again when Manager
does something unexpected. The patches repo owns the device serial, the bundle's name and patch list, the app and its
tested version; this file only gives examples of them, marked as observations from the run on 2026-11-09.

**Last verified on 2026-11-09, Manager v2.6.0.** Before relying on anything below, check for a newer release
([section 1](#1-check-for-a-newer-manager)). Commands below use `ANDROID_SERIAL`, `$TMP`, `$RUN`, `$SKILL`, `$UI`
and `$UI_OUT` from the run directory block in [evidence.md](evidence.md).

## Contents

1. Check for a newer Manager
2. Download and verify Manager
3. Patcher versions
4. Install, permissions and launch
5. Driving the UI over adb
6. Onboarding
7. Keystore
8. Unlock patch selection
9. Add a bundle
10. Bundle order and the shared class loader
11. Select the app and patches
12. Patch
13. Save APK and pull it
14. After a release is published
15. What stays manual
16. Manager state to clean up

## 1. Check for a newer Manager

```bash
gh release list -R ReVanced/revanced-manager -L 15
```

The release marked `Latest` is the one users get. On 2026-11-09 that was `v2.6.0` (2026-04-26); everything newer was a
`-dev` pre-release (up to `v2.7.0-dev.11`). Test the latest stable release unless the owner asks for another.

If it is newer than v2.6.0, verify it as in section 2 and re-check every Manager-specific statement here as you go.
The ones most likely to have moved:

- the fixed tap coordinates (sections 5, 9 and 11, and `ADD_FAB_X`/`ADD_FAB_Y` in
  [`readd-bundle.sh`](../scripts/readd-bundle.sh));
- UI labels, which `ui.sh` and `readd-bundle.sh` match exactly;
- the bundled Patcher version (section 3);
- the signing key and certificate (section 2);
- bundle order by uid, the undeletable built-in bundle and the selection lock (sections 8 and 10);
- the logcat line that carries a bundle's uid (section 10).

Record in the final report which Manager version you tested and which statements you re-verified or found changed.

## 2. Download and verify Manager

Download the APK and its signature into a directory of their own. This one download is kept beside the run
directories on purpose, so a later run can reuse it; verify it again every time, whoever downloaded it:

```bash
V=2.6.0                      # the release from section 1
D=$TMP/manager-$V; mkdir -p "$D"
for f in revanced-manager-$V.apk revanced-manager-$V.apk.asc; do
  curl -fsSL -o "$D/$f" "https://github.com/ReVanced/revanced-manager/releases/download/v$V/$f"
done
sha256sum "$D"/revanced-manager-$V.apk*
gh release view "v$V" -R ReVanced/revanced-manager --json assets \
  --jq '.assets[] | .name + " " + (.size|tostring) + " " + .digest'
```

The APK's SHA-256 must equal GitHub's `digest` for the asset. v2.6.0:
`cba4c461553ea74eb25a7b2e1842419c7f4f40adc619b10d518c114204b7e846`.

Check the GPG signature in a keyring of its own, never the user's:

```bash
export GNUPGHOME=$RUN/gnupg; mkdir -p -m 700 "$GNUPGHOME"       # a fresh keyring per run
gpg --list-packets "$D/revanced-manager-$V.apk.asc" | grep -iE 'keyid|issuer|fpr'
curl -fsSL https://api.revanced.app/keys -o "$D/revanced-keys.asc"
gpg -q --import "$D/revanced-keys.asc"
gpg --list-keys --with-subkey-fingerprints
gpg --verify "$D/revanced-manager-$V.apk.asc" "$D/revanced-manager-$V.apk"
```

- `https://api.revanced.app/keys` returns an armored public key block (the run saved it as `keys.json`, and `jq`
  couldn't parse it). It is the key ReVanced's own API names under `keys` in `https://api.revanced.app/v5/about`.
- Expect `Good signature from "ReVanced <contact@revanced.app>"`. `[unknown]` trust is normal in a fresh keyring:
  what counts is the fingerprints.
- v2.6.0 was signed by subkey `386A60CF28E47029FEBA1A60C789F77D345DB88C` (rsa4096, 2024-02-13) of primary key
  `A7835DFCACA14BDA3CD6EDD3633C6920FBE6A2FF` (ed25519, 2023-08-27, expires 2028-04-20). The subkey was already in the
  API's copy.
- If `gpg --verify` says `No public key`, the signing subkey is newer than the API's copy. The run also fetched
  `https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x<subkey fingerprint>` (keys.openpgp.org answered 404).
  Accept a keyserver copy only if the subkey shows under the same primary fingerprint that `api.revanced.app/keys`
  publishes. A different primary key: stop and ask the owner.

Check the APK signing certificate (how to find `apksigner` is in [apk-provenance.md](apk-provenance.md)):

```bash
"$apksigner" verify --print-certs -v "$D/revanced-manager-$V.apk" |
  grep -E 'Verified using|SHA-256|DN|Number of signers'
```

v2.6.0: one signer, v2 scheme only, `CN=ReVanced Manager, OU=ReVanced, O=ReVanced, L=Unknown, ST=Unknown, C=Unknown`,
certificate SHA-256 `b6362c6ea7888efd15c0800f480786ad0f5b133b4f84e12d46afba5f9eac1223`. A different certificate on a
newer release means a different signing key: stop and ask the owner.

## 3. Patcher versions

Three Patchers meet in a test: the one the patches repo builds against, the one in the CLI it pins, and the one in
Manager. Compare them whenever any of the three changes:

```bash
gh api "repos/ReVanced/revanced-manager/contents/gradle/libs.versions.toml?ref=v$V" --jq .content | base64 -d |
  grep -iE 'patcher|library'
gh api "repos/ReVanced/revanced-cli/contents/gradle/libs.versions.toml?ref=v<cli version>" --jq .content | base64 -d |
  grep -iE 'patcher|library'
grep revanced-patcher gradle/libs.versions.toml      # in the patches repo
```

The CLI version is the one the repo's `justfile` pins. On 2026-11-09: Manager 2.6.0 had patcher-android
`22.0.2-dev.1` (library 4.0.0), CLI 6.0.0 had Patcher `22.0.0` (library 4.0.1), and the repo built against `22.0.1`.
All three loaded the bundle. When a bundle loads in one and not another, a different Patcher major version is the
first thing to suspect.

## 4. Install, permissions and launch

```bash
adb install -r "$D/revanced-manager-$V.apk"
adb shell dumpsys package app.revanced.manager.flutter | grep -E 'versionName|versionCode|minSdk|primaryCpuAbi'
adb shell pm grant app.revanced.manager.flutter android.permission.POST_NOTIFICATIONS
adb shell appops set app.revanced.manager.flutter REQUEST_INSTALL_PACKAGES allow
adb shell appops set app.revanced.manager.flutter MANAGE_EXTERNAL_STORAGE allow
adb shell am start -W -n app.revanced.manager.flutter/app.revanced.manager.MainActivity
```

- Package `app.revanced.manager.flutter`. v2.6.0 installed as versionName `2.6.0`, versionCode `200600099`, minSdk 26,
  targetSdk 36, `arm64-v8a`. If Manager is already installed at the verified version, skip the install.
- `REQUEST_INSTALL_PACKAGES` is "unknown sources"; `QUERY_ALL_PACKAGES` is granted at install.
- Launch with `am start -n` as above. `adb shell monkey -p app.revanced.manager.flutter -c
  android.intent.category.LAUNCHER 1` fails (`VM exiting with result code -5`) and leaves Manager closed. `am start`
  on a running Manager prints `Warning: Activity not started, its current task has been brought to the front`, which
  is harmless.
- On Redroid, Manager patched in its own process with its own arm64 aapt2: no qemu, no extra setup.

## 5. Driving the UI over adb

[`ui.sh`](../scripts/ui.sh) taps by the text uiautomator reports, waits for screens and takes screenshots; its header
documents the commands and exit codes. Set `UI_OUT` to this run's evidence directory ([evidence.md](evidence.md)) so
screenshots and the last dump are kept. Quirks seen on 2026-11-09:

- **Dumps lag the screen.** A dialog can take a second or more to appear, and a dump taken right after a tap shows the
  old screen. After every tap, `$UI wait` for a label of the next screen instead of sleeping and dumping once.
- **Wait for the end state, not for something always on screen.** On the patching screen "Save APK" is there from the
  start; section 12 says what to wait for.
- **The dump's order isn't the screen's order.** `$UI tap '^Delete$' 2` hit the wrong bundle's trash icon. Find a row
  by its name and pick nodes by position relative to it (as `readd-bundle.sh` does), never by match number.
- **Some labels repeat.** On onboarding, `^ReVanced Manager$` matches the title first and the self-update row second.
- **Some controls aren't in the dump.** Measured on a 1080x2400, 420 dpi screen with v2.6.0:
  - the **Add patches** button on the Patches tab in edit mode: `840 2158`;
  - in **Select patches**, the select-all checkbox of the first bundle's header: `106 348`, and that header's
    collapse arrow: `974 348`. With the first section collapsed, the second header's checkbox was at `106 540`.

  Tap these with `adb shell input tap <x> <y>`, and only after a dump shows which bundle's name sits at that height:
  the order of sections follows the bundle uid (section 10). Re-measure from a screenshot when Manager or the screen
  size changes (`adb shell wm size`).
- **Ticks aren't in the dump.** Compose checkboxes and switches have no node of their own, so the `checked` column
  stays false. Read the state from a screenshot, or from the count Manager prints ("21 patches selected").
- **Text entry:** tap the field, `$UI type '<text>'` (it sends spaces as `%s`, as `adb shell input text` needs), then
  `adb shell input keyevent BACK` to close the keyboard. The keyboard moves dialog buttons (the URL dialog's Add moved
  from y 1407 to 1455), so look buttons up after closing it.
- **Navigation:** `adb shell input keyevent BACK` leaves screens; too many BACKs leave Manager for the launcher.
  Bring it back with the `am start` from section 4.
- **The system file picker** (DocumentsUI, `com.android.documentsui`) serves both "Select from storage" and **Save
  APK**:
  - The first time it opened on **Recent** with **No items**; tap **Show roots**, then **Downloads**. Later it
    opened in Downloads.
  - Tap the file's *name*. The first match for a name can be its **Preview the file …** icon, which opens a preview
    instead of picking it.
  - A file near the bottom of the screen can sit under the navigation bar: the run's tap at y 2342 left the picker and
    ended on Manager's home screen. Tap **List view**, which moved the file higher, and pick it again.

## 6. Onboarding

Manager v2.6.0's first start has three screens:

1. **Permissions** ("ReVanced Manager needs a few permissions to work properly"): Install unknown apps, Notifications,
   Battery optimization. After section 4's commands only **Battery optimization** still offered **Grant**. Don't
   try to grant it over adb: the run put Manager on the system's `deviceidle` whitelist and onboarding didn't
   notice, even after Manager was brought back to the front. Tap **Skip for now**, then **Skip anyway** in "Skip
   permissions?". Patching ran fine without it.
2. **Updates** ("Configure automatic updates to keep ReVanced Manager and patches up to date"): untick all three rows,
   **ReVanced Manager** (match 2 of `^ReVanced Manager$`), **ReVanced Patches** and **APK Downloaders**, then **Next**.
   Self-update would move the device off the verified version; the other two add outside inputs to the test.
   Unticking **ReVanced Patches** doesn't keep ReVanced's bundle out: Manager fetched it anyway (v6.2.1, 294
   patches) and it stays loaded.
3. **Select an app**: tap **Skip for now**. The home screen has the tabs **Apps** and **Patches**, and **Settings** and
   **Announcements** at the top.

## 7. Keystore

Manager signs its output with its own generated key unless one is imported. An APK signed with a different key than
the installed app's can't be installed with `adb install -r`, and an uninstall would lose the owner's login. So
import the keystore that signs the repo's CLI builds (the repo's `AGENTS.md` and `justfile` say where it is):

```bash
adb push <keystore> /sdcard/Download/
```

1. **Settings** → **Import & export** ("Keystore, patch options and selection"). The **Keystore** section shows
   **Username (Alias)** `ReVanced` and **Password** for the generated key.
2. Tap the first **Import** (the second one belongs to **Patch selections**); pick the keystore in the file picker.
3. The dialog **Enter keystore credentials** asks for **Username (Alias)** and **Password**. Tap the alias field,
   `$UI type 'ReVanced Key'`, close the keyboard, leave **Password** empty, tap **Import**.
4. The Keystore section now shows the alias **ReVanced Key**.

`ReVanced Key` and the empty password are revanced-cli 6.0.0's defaults (`--keystore-entry-alias`,
`--keystore-entry-password`); the repo's test keystore is one the CLI created on first use. Another keystore needs
its own alias and password. Remove the copy from shared storage as soon as the import worked:
`adb shell rm /sdcard/Download/<keystore>`.

## 8. Unlock patch selection

By default Manager locks patch selection and options: a user who just adds a bundle patches with the default
selection of every loaded bundle, and can't change options. Test that default too (section 11).

To choose patches: **Settings** → **Advanced** ("API URL, memory limit, debugging") → **Allow changing patch selection
and options** → **Confirm** in "Allow changing patch selection and options?". Leave the other Advanced settings as they
are; v2.6.0 also has **Turn off version compatibility check**, **Require suggested app version**, **Allow using
universal patches**, **Run Patcher in another process (experimental)**, **Minimum log level** and **Export debug
logs**. The run patched in-process, the default.

## 9. Add a bundle

First delete any bundle of the repo under test that an earlier run left loaded (how to remove one is below): two
copies of a bundle collide on their own file paths, and the order test in section 10 assumes one.

**Patches** tab → **Edit** (bottom right) → **Add patches** (fixed coordinates, section 5) → the dialog **Add
patches** offers **Enter URL** ("Patches can receive updates", marked **Recommended**) and **Select from storage**
("Add patches from local storage") → **Next**.

- **Local file**, for builds that aren't released: `adb push <bundle>.rvp /sdcard/Download/`, choose **Select from
  storage**, **Next**, tap **Not selected**, pick the file (it then reads **Selected**), run `adb logcat -c`, tap
  **Add**.
- **URL**, what users do: take the URL from the Install section of the patches repo's README, choose **Enter URL**,
  **Next**, tap **Patches URL**, type the URL, close the keyboard, run `adb logcat -c`, tap **Add**. **Auto update**
  sits under the field;
  the run left it as it was, and logcat showed `autoUpdate=true`. On 2026-11-09 the README's
  `…/releases/latest/download/patches-bundle.json` loaded release v0.1.0.

Right after the add, read the bundle's uid from logcat (section 10) and note it: Manager logs it only when a bundle
is added, and a later `adb logcat -c` loses it.

Manager leaves edit mode after every add. The bundle's row then shows its name, version and patch count, for example
`edbfi patches` / `0.0.0 • 15 patches` for a local build and `v0.1.0 (11h ago) • 12 patches` for the URL. Check them
against the repo's README and `docs/<app>.md` (the count includes patches that are off by default). Tapping the row
opens its info page (name, description, website, contact, repository, license, patch count): check those against the
bundle's manifest in the repo's build file.

To remove a bundle: **Edit**, the trash icon (content-desc **Delete**) in its row, **Confirm** in the dialog that says
`“<name>” will be deleted`.

**ReVanced Patches can't be removed.** It is bundle uid 0; its trash icon is greyed out and does nothing, and its info
page has **Refresh** instead of **Delete**. It loads whether or not any of its patches are selected.

## 10. Bundle order and the shared class loader

Manager (and the CLI, see [host-checks.md](host-checks.md)) loads every bundle through one class loader. A file at
the same path in two bundles resolves to whichever bundle comes first, so a bundle's patches can read another bundle's
extension or resource. That broke release v0.1.0 of edbfi/revanced-patches: ReVanced's bundle also shipped
`extensions/syncforreddit.rve`, and with it first, patching failed with `Could not find WebsitePreviews.isEnabled in
the extension` (local build) or `Could not find Imgur.clientId in the extension` (v0.1.0). PR #21 moved the extension
to a path of its own.

In Manager the order follows each bundle's `uid`, ascending. ReVanced's is 0; every added bundle gets a random 32-bit
uid when it is added, so its sign decides whether it comes before ReVanced's (negative) or after it (positive). The
Patches tab and the sections of **Select patches** list bundles in the same order. Every re-add draws a new uid.

Read the uid from logcat, which Manager writes when a bundle is added:

```bash
adb logcat -c
# ... tap Add ...
adb logcat -d | grep -oE 'PatchBundleEntity\(uid=-?[0-9]+, name=[^,]*, versionHash=[^,]*, source=[^,]*'
```

It prints one `Source:` line per loaded bundle. From the run:

```text
D ReVanced Manager: Source: PatchBundleEntity(uid=0, name=ReVanced Patches, versionHash=v6.2.1, source=api, autoUpdate=false, releasedAt=1780425000000)
D ReVanced Manager: Source: PatchBundleEntity(uid=1643288158, name=, versionHash=null, source=local, autoUpdate=false, releasedAt=null)
D ReVanced Manager: Source: PatchBundleEntity(uid=-512351965, name=Unnamed, versionHash=v0.1.0, source=https://github.com/edbfi/revanced-patches/releases/latest/download/patches-bundle.json, autoUpdate=true, releasedAt=1794219921000)
```

A local bundle has an empty `name` and `versionHash=null`; a URL bundle has `name=Unnamed`, the release tag and the
URL.

Test both orders. The one that matters most is ReVanced's bundle first (a positive uid), the order that failed
before; if there is time for one only, test that one. Patch with the order the first add gave, then re-add the bundle
until it has the other sign:

```bash
"$SKILL/scripts/readd-bundle.sh" '<bundle name as Manager shows it>' <bundle>.rvp <positive|negative>
```

It prints each try's uid; each try is a coin flip, so six tries fail about once in 64. It handles local bundles only;
for a URL bundle repeat section 9's URL steps by hand, deleting the bundle first. In the run, v0.1.0 by URL got a
negative uid first and a positive one on the next add; a local build needed 2 tries.

**After a re-add, the app's selection was back to the default** in the run (the unlock from section 8 stays): untick
ReVanced Patches again (section 11) and check the count before patching.

## 11. Select the app and patches

**Apps** tab → **Select from storage** ("Select an APK file using file picker") → pick the original APK pushed to
`/sdcard/Download` ([apk-provenance.md](apk-provenance.md) says how to check it first). The **App info** screen shows
the app, its version, **Select patches** with "N patches selected", **Select APK source** ("Using an APK file") and
**Patch**.

Patch both selections:

1. **The default**, what a user gets out of the box: don't touch the selection. ReVanced's bundle selects its own
   patches for the same app next to the repo's.
2. **The repo's bundle only**, what the README tells users to do: after section 8, **Select patches**, untick the
   **ReVanced Patches** header (fixed coordinates, section 5; check which bundle's header is at the top first), **Save**
   (the button reads "Save (N)" on screen, "Save (14)" in the run, and "Save" in the dump). "N patches selected" must
   equal the repo's default-on count.

Patch options: a patch row with options has a **Settings** gear. Its screen lists each option with its description;
required ones end in `*`, an unchanged option shows **Using default value**, and an option with preset values has
**Toggle dropdown menu**. Check names, descriptions and defaults against the repo's `docs/<app>.md`.

A worked example of what a mixed run can show, for one app only (Sync for Reddit, 2026-11-09): ReVanced's bundle v6.2.1
selected its 7 default Sync patches next to the repo's 14, so Manager showed "21 patches selected"; 7 patch names
were shared. Patcher runs patches sorted by name and the sort is stable, so same-named patches run in bundle order.
With ReVanced's bundle first, ReVanced's "Disable Sync for Lemmy bottom sheet" ran before the repo's, and the repo's
then didn't find the call it changes: `PatchException: Expected one call that shows Laa/c;, found 0`. With the
repo's bundle first, all 21 completed, which says nothing about how two overlapping patch sets behave in the app.

## 12. Patch

Tap **Patch**. The **Patcher** screen shows steps (**Preparing**, **Patching** with an **Execute patches** list of
each patch and its status, then **Saving**), and at the bottom **Save APK** and **Save logs**, which are there from the
start. When patching ends, **Install** appears on success. On a failure the run saw the failed step marked with a
red cross and the exception's text under **Execute patches**; the label of the failed status was never read from a
dump, so wait for the exception text as well:

```bash
"$UI" tap '^Patch$'
"$UI" wait '^Install$|^failed$|Exception' 300
"$UI" shot <name>
```

A wait that times out (exit 124) is not a result: take a screenshot and a dump, and read the screen.

Never tap **Install** unless the owner allowed Manager's installer (ground rules in SKILL.md).

On a failure, the exception is a node under **Execute patches** (`$UI dump 'Exception'`), and Manager stops at the
first failed patch. The patch log is in logcat under the tags `ReVanced Patcher` and `ReVanced Manager`:

```bash
adb logcat -d > "$UI_OUT/logcat-<name>.txt"
grep -E 'ReVanced (Patcher|Manager)' "$UI_OUT/logcat-<name>.txt" | grep -v 'Could not decode' | grep -vE '^\s+at '
```

It shows `<patch name> failed:` with the stack trace, then `[Worker] An exception occurred while patching`; a
success ends with `[Worker] Patching succeeded`. Clear logcat (`adb logcat -c`) before tapping **Patch** so the file
holds one run. **Save logs** wasn't used in the run.

On 2026-11-09 Redroid patched 14 patches in about 33 s, 21 in 34 s. Memory, read once with
`adb shell dumpsys meminfo app.revanced.manager.flutter | grep -E 'TOTAL PSS|TOTAL RSS'`, was about 325 MB PSS
(497 MB RSS); that reading came right after a run that failed early, so it isn't a peak.

## 13. Save APK and pull it

`adb shell` runs as uid 2000 (`shell`) and Manager isn't debuggable, so `run-as` can't read its result. The image has
`su`, but reading Manager's private files as root isn't how a user gets the APK, and `adb root` restarts adbd on the
shared device. Use **Save APK**, as a user would:

1. Tap **Save APK**. The file picker opens in Downloads with a name filled in:
   `com.laurencedawson.reddit_sync_v23.06.30-13:39_revanced_patched.apk` in the run, so presumably
   `<package>_<versionName>_revanced_patched.apk` for any app. Tap **SAVE**.
2. On disk the `:` became `_`. Delete an earlier copy of that name before saving, so the pull gets this run's file.

```bash
adb shell ls /sdcard/Download/ | grep revanced_patched
d="$RUN/downloads/manager-<selection>-<order>"; mkdir -p "$d"     # one directory per Manager build
adb pull "/sdcard/Download/<saved name>" "$d/patched.apk"
```

Then check it as [apk-provenance.md](apk-provenance.md) section 5 describes: the signer certificate equals the CLI
build's, the versionCode is unchanged, the bundle's extension classes are in the dex. Install it only with
`adb install -r`, and check `firstInstallTime` afterwards.

## 14. After a release is published

Test what a user's Manager does with the new release: add the README's URL (section 9) and check that the row shows the
new version and patch count from the release's `patches-bundle.json`. A fresh add always fetches the latest release.

Not exercised on 2026-11-09: how an existing URL bundle picks up a new release in place. Its **Auto update** was on
when added, and ReVanced's bundle's info page has **Refresh** and **Auto update**; whether a URL bundle's info page
has the same wasn't checked. If you test it, report what you saw.

## 15. What stays manual

- New app APK downloads ([apk-provenance.md](apk-provenance.md) section 1).
- Any login. The agent never types credentials; the owner logs in through scrcpy.
- Using Manager's own **Install**: only with the owner's permission. Without it, Manager's installer stays untested;
  say so in the report.

## 16. Manager state to clean up

The run left Manager installed with the test keystore imported, its updates and downloaders off, patch selection
unlocked, and ReVanced's bundle plus the last tested bundle loaded. That is a usable state for the next run; keep
Manager unless the owner says otherwise, and list its state in the final report.

Remove what the run put on shared storage:

```bash
adb shell ls /sdcard/Download/
adb shell rm -f /sdcard/Download/<keystore> /sdcard/Download/<bundle>.rvp \
  "/sdcard/Download/<saved name>" /sdcard/ui.xml
```

`/sdcard/ui.xml` is where `ui.sh` dumps. The keystore must go even if the run fails half-way. The run kept the original
APK in Downloads for the next run; say in the report what you kept.
