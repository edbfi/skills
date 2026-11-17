# Morphe Manager on the test device

How to get a verified Morphe Manager onto the device, set it up, add a patches source, patch with it, and get the
output back out, all over adb. Read it before the Manager part of the workflow in SKILL.md, and again when Manager
does something unexpected. The patches repo owns the device serial, the bundle's name and patch list, the apps and
their tested versions; this file only gives examples of them, marked as observations from the run on 2026-11-17.

**Last verified on 2026-11-17, Manager v2.6.0.** Before relying on anything below, check for a newer release
([section 1](#1-check-for-a-newer-manager)). Commands below use `ANDROID_SERIAL`, `$TMP`, `$RUN`, `$SKILL`, `$UI`
and `$UI_OUT` from the run directory block in [evidence.md](evidence.md).

## Contents

1. Check for a newer Manager
2. Download and verify Manager
3. Patcher versions
4. Install and launch
5. Driving the UI over adb
6. Onboarding
7. Keystore
8. Add, check and remove a source
9. Several sources at once
10. Patch an app
11. Save and pull the APK
12. Logs
13. After a release is published
14. What stays manual
15. Manager state to clean up

## 1. Check for a newer Manager

```bash
gh release list -R MorpheApp/morphe-manager -L 10
```

The release marked `Latest` is the one users get. On 2026-11-17 that was `v2.6.0` (2026-11-15); newer ones were
`-dev` pre-releases (`v2.7.0-dev.2`). Test the latest stable release unless the owner asks for another.

If it is newer than v2.6.0, verify it as in section 2 and re-check every Manager-specific statement here as you go.
The ones most likely to have moved:

- UI labels and screens, which `ui.sh` matches exactly (sections 7, 8, 10 and 11), and the one measured tap
  coordinate (section 11);
- the bundled Patcher version (section 3);
- the signing certificate (section 2);
- the logcat lines sections 8, 10 and 12 grep for;
- whether Manager's own source has patches for the apps under test (section 9).

Record in the final report which Manager version you tested and which statements you re-verified or found changed.

## 2. Download and verify Manager

Download the APK and its signature into `$TMP/inputs/morphe-manager-$V/`. This one download is kept outside the run
directory on purpose, so a later run can reuse it; verify it again every time, whoever downloaded it:

```bash
V=2.6.0                      # the release from section 1
D=$TMP/inputs/morphe-manager-$V; mkdir -p "$D"
for f in morphe-manager-$V.apk morphe-manager-$V.apk.asc; do
  curl -fsSL -o "$D/$f" "https://github.com/MorpheApp/morphe-manager/releases/download/v$V/$f"
done
sha256sum "$D"/morphe-manager-$V.apk*
gh release view "v$V" -R MorpheApp/morphe-manager --json assets --jq '.assets[] | .name + " " + .digest'
"$apksigner" verify --print-certs -v "$D/morphe-manager-$V.apk" | grep -E 'Verified using|SHA-256|DN|Number of signers'
```

- The APK's SHA-256 must equal GitHub's `digest` for the asset. v2.6.0:
  `1fd2547689e87217426d817aa8cad3f53a160b08fc09032cf0f81d71714cb68c`.
- The signing certificate (how to find `apksigner` is in [apk-provenance.md](apk-provenance.md)). v2.6.0: one
  signer, v2 scheme only, `CN=Morphe, O=MorpheApp`, certificate SHA-256
  `0b6c9515afb195fac59601696ba0a7907a0b217ccf720b43148427ccf64343e7`. A different certificate on a newer release
  means a different signing key: stop and ask the owner.
- The `.asc` is a GPG signature by key `E244593DB55072D93DCED3F68727D90AC9BE1F14`
  (`gpg --list-packets "$D/morphe-manager-$V.apk.asc"`). No published copy of that key was found on 2026-11-17 (the
  Manager's README names none), so the signature went unchecked. If you find the key where Morphe publishes it, check
  the signature in a keyring of its own (`GNUPGHOME=$RUN/gnupg`), never the user's, and say where the key came from.

## 3. Patcher versions

Three Patchers meet in a test: the one the patches repo builds against, the one in the CLI it pins, and the one in
Manager. Compare them whenever any of the three changes:

```bash
grep -i morphe-patcher morphe/gradle/libs.versions.toml     # in the patches repo
adb logcat -d | grep -m1 'Morphe Patcher: Build:'           # after Manager patched once
```

Manager logs `Build: manager=2.6.0 patcher=2.4.0 nativeLibs=false` at the start of every patch run. The patches repo
pins `morphe-patcher` to a version the latest Manager and Morphe desktop both ship (its `AGENTS.md`, Morphe section),
2.4.0 on 2026-11-17, and Manager warns on a bundle whose `Patcher-Version` is newer than its own. For the CLI, read
its version from the repo's `justfile` (`morphe_cli_version`, 2.2.0 on 2026-11-17) and its Patcher from its release's
build files. When a bundle loads in one and not another, a different Patcher version is the first thing to suspect.

## 4. Install and launch

```bash
adb install -r "$D/morphe-manager-$V.apk"
adb shell dumpsys package app.morphe.manager | grep -E 'versionName|versionCode|firstInstallTime'
adb shell am start -W -n app.morphe.manager/.MainActivity_Default
```

- Package `app.morphe.manager`. v2.6.0 installed as versionName `2.6.0`, versionCode `39922687`, minSdk 26,
  targetSdk 37. If Manager is already installed at the verified version, skip the install.
- The run of 2026-11-17 found Manager installed and set up the day before, so which permissions it asks for on first
  start wasn't recorded. If it asks, grant what patching and saving need (notifications, storage, installing apps),
  and record what you granted.
- Manager runs the Patcher in a JVM process of its own (`Patcher process: pid=… vm=JVM heap=3072MB` in the log), with
  its own Java 25. On Redroid it patched without any host setup.

## 5. Driving the UI over adb

[`ui.sh`](../scripts/ui.sh) taps by the text uiautomator reports, waits for screens and takes screenshots; its header
documents the commands and exit codes. Set `UI_OUT` to this run's evidence directory ([evidence.md](evidence.md)) so
screenshots and the last dump are kept.

- **The home screen** has three tabs at the bottom: **Sources**, **Apps** and **Settings**.
- **Dumps lag the screen.** After every tap, `$UI wait` for a label of the next screen instead of sleeping and dumping
  once.
- **Some labels repeat.** On the Sources tab with the add sheet open, the top bar's add button and the sheet's bottom
  button can both match `^Add$`. Pick nodes by position (`$UI dump '^Add$'`, then the one at the bottom), never by
  match number alone.
- **Ticks aren't always in the dump.** Compose checkboxes and switches may have no node of their own, so the
  `checked` column can stay false. Read the state from a screenshot, or from a count Manager prints
  ("2 of 2 selected").
- **Text entry:** tap the field, `$UI type '<text>'`, then `adb shell input keyevent BACK` to close the keyboard. The
  keyboard moves buttons, so look them up after closing it.
- **Navigation:** `adb shell input keyevent BACK` leaves screens; too many BACKs leave Manager for the launcher. Bring
  it back with the `am start` from section 4.
- **The system file picker** (DocumentsUI) serves both "Select patch source files", the original APK, and **Save**. It
  opened in Downloads in the run. Tap the file's *name*: the first match for a name can be its preview icon. If it
  opens on Recent with no items, tap **Show roots**, then **Downloads**.

## 6. Onboarding

Not seen on 2026-11-17: Manager had been set up on 2026-11-16. If a first start shows onboarding, turn off Manager's
self-update (it would move the device off the verified version) and anything that adds outside inputs to the test,
take a screenshot of each screen, and report the labels so this section can be written from them.

## 7. Keystore

Manager signs its output with its own generated key unless one is imported. An APK signed with a different key than
the installed app's can't be installed with `adb install -r`, and an uninstall would lose the owner's login. So import
the keystore that signs the repo's CLI builds (the repo's `AGENTS.md` and `justfile` say where it is):

```bash
adb push <keystore> /sdcard/Download/
```

1. **Settings**, search for `Signing key`, open it, tap **Import** and pick the keystore in the file picker.
2. Enter the alias `ReVanced Key` and leave the password empty. That is what the patches repo's test keystore holds
   (revanced-cli created it, and `just morphe-patch` passes the same alias); another keystore needs its own.
3. Manager then shows the key's SHA-256, `DB:94:7B:6F…` on 2026-11-17: the same certificate as the CLI builds'
   `db947b6f…38eb` (apk-provenance.md, section 5).

Remove the copy from shared storage as soon as the import worked: `adb shell rm /sdcard/Download/<keystore>`.

## 8. Add, check and remove a source

First delete any source of the repo under test that an earlier run left in Manager (how to is below): two copies of a
bundle are two sets of the same patches, and section 10 assumes one.

**Sources** tab → **+** in the top bar → the **Add patch source** sheet:

- **Source URL** ("A repository or a link to a patch bundle .json. Paste several at once to add them all"): what users
  do. Paste the URL the README's Morphe Manager section gives (`https://github.com/edbfi/apk-patches` in
  `edbfi/apk-patches`) or a `patches-bundle.json` URL.
- **Select patch source files**: a local `.mpp`, for builds that aren't released. `adb push <bundle>.mpp
  /sdcard/Download/` first, then pick it in the file picker.
- **Choose apps** ("Pick which of its apps to keep once the source has loaded"): with it on, Manager shows a chooser
  once the source has loaded: the source's name, "N of N selected", **Bring new apps** ("Apps it adds later show up
  on the home screen"), and one row per app with its patch count (`rif is fun` / `12 patches`, `Sync for Reddit` /
  `15 patches` on 2026-11-17). A tap on a row unticks the app (and a second tap brings it back); **Close** ends it.
  Keep every app the repo supports ticked.

Confirm with the **Add** at the bottom of the sheet, not the top bar's add button. Clear logcat just before; Manager
logs one line per source once the new one loads:

```bash
adb logcat -d | grep -oE 'Bundle: PatchBundleEntity\([^)]*\)'
```

```text
Bundle: PatchBundleEntity(uid=0, name=Morphe Patches, displayName=Morphe Patches, versionHash=v2.3.0, source=api, enabled=true, sortOrder=0, …)
Bundle: PatchBundleEntity(uid=-1878644511, name=edbfi patches, displayName=null, versionHash=null, source=local, enabled=true, sortOrder=1, …)
```

The new source's card, expanded, shows its name, `<version> • <age>`, **Patches** (the count over all its apps),
**Version**, **Signed by** with a fingerprint for a signed bundle, and **Apps**. Check them against the repo: on
2026-11-17 a local build showed `edbfi patches`, `0.0.0`, 27 patches (12 + 15, off-by-default ones included) and 2
apps, and no **Signed by**: local builds are unsigned. A release must show the fingerprint the README gives, `bb0f
2749 5a09 70ea` for `edbfi/apk-patches`. Manager's own source showed `Signed by 9d49 663c 29c8 9930`.

To remove a source: expand its card; its row of four icon buttons ends in a red trash icon. Tap it and confirm. Find
the icons in a dump of that screen; the run didn't record their labels.

## 9. Several sources at once

**Manager's own source can't be avoided:** Morphe Patches (uid 0, `source=api`) is there from the start. On
2026-11-17, v2.3.0 had 212 patches for 3 apps and none for rif is fun or Sync for Reddit, so nothing of it was
selected for them and there was nothing to untick; the README tells users the same. Check it again on every run:
open its **Apps** row, or look at the app's screen (section 10), which names the source it patches with. If it has
patches for an app under test now, patch the default selection (what users get) and the repo's patches only, and
report both.

Every source a user loads may share one class loader, as in other patchers: a file at the same path in two bundles
could then come from the wrong one. Whether Manager orders sources by `sortOrder` (the add order) and loads them
together wasn't tested. The host checks ([host-checks.md](host-checks.md)) look for shared paths without the device.

## 10. Patch an app

**Apps** tab: it lists the apps the loaded sources support, by name (`rif is fun`, and Sync for Reddit as `Sync` on
2026-11-17). Tap one:

- **No original stored:** "Need help finding the APK?", the version it needs with an **Unpatched** badge, **Yes, help
  me find it** and **No, I already have it**. Tap **No, I already have it**, then pick the checked original APK
  ([apk-provenance.md](apk-provenance.md)) that you pushed to `/sdcard/Download/`.
- **An original or an earlier result stored:** the app's screen opens at once: name, version, **Saved**, **Package
  name**, **Newest supported**, **APK size**, **CPU architecture**, **Applied patches**, **Patch source used** and a
  **Patch** button. Manager reuses the original it stored before
  (`/data/user/0/app.morphe.manager/app_original-apks/<package>_<version>_original.apk`), which happened for rif is fun
  on 2026-11-17. You can't hash that file without root; check instead that the log's `input=` names it and its
  `size=` equals your checked original's byte count (12795917 for rif is fun 5.6.22).
- The app's screen can show a **Web links not verified** card with **Fix links** and **Ignore**, about the installed
  app's link handling. Leave it alone: it isn't part of the patch and changes system settings.

Clear logcat, tap **Patch**, and wait for the result screen. The progress screen shows a percentage, `N / N patches`
and **Cancel**; on success the result screen shows **Patched**, the app's name, **Version**, **Patches** (`12
patches`), **Source** (`edbfi patches 0.0.0`), **Install**, a save icon, a share icon and **Home**:

```bash
adb logcat -c
"$UI" tap '^Patch$'
"$UI" wait '^Patched$|failed|Exception' 300
"$UI" shot <name>
```

A wait that times out (exit 124) is not a result: take a screenshot and a dump, and read the screen. The failure
screen wasn't seen on 2026-11-17; on a failure, keep its screenshot and the log (section 12). Never tap **Install**
unless the owner allowed Manager's installer (ground rules in SKILL.md).

On 2026-11-17 Redroid patched rif is fun's 12 patches in 6.3 s and Sync for Reddit's 14 in 2.5 s.

## 11. Save and pull the APK

`adb shell` runs as uid 2000 and Manager isn't debuggable, so `run-as` can't read its result, and reading it as root
isn't how a user gets the APK. Use the save icon, as a user would:

1. On the result screen tap the save icon right of **Install** (measured from a 1080x2400 screenshot: `812 1958`;
   look for its node in a dump first). The file picker opens in Downloads with a name filled in,
   `<app name>-v<app version>-edbfi_patches-v<bundle version>.apk`; tap **SAVE**.
2. On disk the spaces became `_` (`rif_is_fun-v5.6.22-edbfi_patches-v0.0.0.apk`). Delete an earlier copy of that name
   before saving, so the pull gets this run's file.

```bash
adb shell ls /sdcard/Download/ | grep edbfi_patches
d="$RUN/downloads/manager-<app>"; mkdir -p "$d"          # one directory per Manager build
adb pull "/sdcard/Download/<saved name>" "$d/patched.apk"
```

Then check it as [apk-provenance.md](apk-provenance.md) section 5 describes: the signer certificate equals the CLI
build's, the version is unchanged, the extension classes are in the dex, and the dex and resources equal the CLI
build's. Install it only with `adb install -r`, and check `firstInstallTime` afterwards.

## 12. Logs

The patch log is in logcat under the tags `Morphe Patcher` and `Morphe Manager`:

```bash
adb logcat -d > "$RUN/logs/manager-<app>-logcat.txt"
grep -E 'Morphe (Patcher|Manager):' "$RUN/logs/manager-<app>-logcat.txt" | grep -vE '^\s+at '
```

A run starts with `Build: manager=… patcher=…`, `Patching started at … pkg=… version=… input=… size=… split=…` and
`Source: name="edbfi patches" version="0.0.0"`, then one `<patch> succeeded` per patch, and ends with
`Patching succeeded: output=… size=… elapsed=…ms` and `[Worker] Patching succeeded`. Count the `succeeded` lines
against the docs' default-on patches. The log also names `Morphe Patcher: Original APK already exists in repository
(version …), skipping duplicate save` when Manager reused a stored original.

Manager has two ways to hand logs to a user, worth naming in a bug report: with Expert mode on, the patching screen
has a **Copy log** button; and **Settings** → **Help & info** → **Export debug logs**. The run used logcat.

## 13. After a release is published

Test what a user's Manager does with the new release: delete this repo's source, add the README's Morphe Manager URL
(section 8), and check that the card shows the new version, the patch count and apps count from the docs, and the
README's **Signed by** fingerprint. Manager downloads the release's `.mpp` through the repo's `patches-bundle.json`
on `main`, checks the signature inside it and remembers the key. Then patch one app from it (section 10) and check
the output as in section 11.

Not exercised on 2026-11-17: a release source, how an existing source picks up a newer release, and what Manager
shows for a release signed by another key. If you test them, report what you saw.

## 14. What stays manual

- A new app APK, if the browser stays on Cloudflare's check ([apk-provenance.md](apk-provenance.md) section 1).
- Any login. The agent never types credentials; the owner logs in through scrcpy.
- Using Manager's own **Install**: only with the owner's permission. Without it, Manager's installer stays untested;
  say so in the report.

## 15. Manager state to clean up

The run of 2026-11-17 left Manager installed with the test keystore imported, Morphe Patches and the last tested
source loaded, and originals stored for both apps. That is a usable state for the next run; keep Manager unless the
owner says otherwise, and list its state in the final report.

Remove what the run put on shared storage:

```bash
adb shell ls -la /sdcard/Download/
adb shell rm -f /sdcard/Download/<keystore> /sdcard/Download/<bundle>.mpp \
  "/sdcard/Download/<saved name>" /sdcard/ui.xml
```

`/sdcard/ui.xml` is where `ui.sh` dumps. The keystore must go even if the run fails half-way. Original APKs earlier
runs left in Downloads for reuse can stay; say in the report what you kept.
