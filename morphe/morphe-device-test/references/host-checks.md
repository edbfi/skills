# Host checks: two bundles in the CLI

Checks that run on the host with the Morphe CLI, without the device, and catch a bundle that only works when it is
the only one loaded. Run them before the Manager part of the workflow, and again whenever Morphe's own bundle, the CLI
or the repo's extensions change. They take minutes.

**Not yet run with the Morphe CLI** (2026-11-17): sections 2, 4 and 5 are derived from the same checks for other
patchers and from the CLI's usage text; only section 3's path comparison was run, on the host. Report every result,
and the commands you ran, so this file can be confirmed.

## Contents

1. Why a second bundle matters
2. Get Morphe's bundle
3. Shared file paths
4. Two bundles, both orders
5. The shadowing run
6. What these checks don't cover

## 1. Why a second bundle matters

A patcher that loads several bundles may read a patch's extension or resource through one class loader, so a file at
the same path in two bundles comes from whichever bundle is first. With another patcher that broke a release of
`edbfi/apk-patches`: another vendor's bundle shipped the same extension path for the same app, and with it first the
repo's patches failed or merged the wrong extension. The repo's answer, in both of its bundles, is the `edbfi` in
every extension and resource path, which its `PatchMetadataTest` checks, and extension patches that fail when none of
their classes arrive. These checks confirm both from the outside. The repo's patch recipe passes one bundle (see its
`justfile`), so it can never see this.

Morphe Manager always has Morphe's own source loaded next to the repo's ([manager.md](manager.md) section 9), so its
bundle is the one to test against.

## 2. Get Morphe's bundle

Take the release Manager loads (its Morphe Patches card shows the version, 2.3.0 on 2026-11-17). The Morphe CLI
downloads it from the repository URL and checks its signature itself, the same way Manager does:

```bash
env -u ANDROID_SERIAL java -jar "$CLI" list-patches --patches https://github.com/MorpheApp/morphe-patches \
  -f <package>
```

In `list-patches`, `-p` means `--with-packages`, not the bundle as in `patch`: name the bundle with `--patches`. `-f`
keeps the patches for one app (and those for any app; `-u` is on by default).

`$CLI` is the CLI jar the repo's patch recipe fetches and pins (see its `justfile`;
`.tools/morphe-desktop-<version>-all.jar` in `edbfi/apk-patches`, run with `MORPHE_DATA_DIR` as the recipe sets it). Its
usage text (`--help` on each subcommand) was read on 2026-11-17; these commands weren't run. For the file checks below
you also need the `.mpp` as a file: an earlier download sat in `$TMP/inputs/morphe-patches-2.3.0/patches-2.3.0.mpp` on
2026-11-17. The CLI checks a bundle's signature only when it downloads it, so check a file before it runs: its
SHA-256 must equal the release asset's `digest`
(`gh release view <tag> -R MorpheApp/morphe-patches --json assets --jq '.assets[] | .name + " " + .digest'`), as
`manager.md` section 2 does for Manager's APK. Its zip comment also holds Morphe's signature (`MorpheSig1 …`,
`unzip -z <file>`). Record its version and SHA-256 in the report.

## 3. Shared file paths

Compare every file the two bundles hold outside their own class trees; any path in both is a shadowing risk:

```bash
OURS=<the repo's built bundle>.mpp
THEIRS=<Morphe's bundle>.mpp
paths() { unzip -Z1 "$1" | grep -vE '/$|\.class$|^META-INF/' | LC_ALL=C sort; }
LC_ALL=C comm -12 <(paths "$OURS") <(paths "$THEIRS")
```

Expected: only `classes.dex` (each bundle's compiled patches, not read through extension paths). On 2026-11-17 the
repo's bundle held `classes.dex` and `extensions/edbfi/<app>.mpe` per app; Morphe's 2.3.0 held `classes.dex`,
extensions such as `extensions/reddit.mpe` and `extensions/shared.mpe`, and resources under its own feature
directories, and `classes.dex` was the only shared path. Any other shared path is a finding: name it and the patch
that reads it.

## 4. Two bundles, both orders

```bash
H=$RUN/host-checks; mkdir -p "$H"
APK=<the checked original APK>
run() {
  local name=$1; shift
  # No ANDROID_SERIAL for the CLI: nothing in a host check needs the device.
  env -u ANDROID_SERIAL java -jar "$CLI" patch "$@" --keystore "$H/ks.keystore" -r "$H/$name.json" \
    -o "$H/$name.apk" "$APK" > "$H/$name.log" 2>&1
  echo "== $name exit=$?"
  jq -c '{success, failedPatches}' "$H/$name.json"
}
run theirs-first -p "$THEIRS" -p "$OURS" --exclusive -e "<patch>" -e "<patch>"
run ours-first -p "$OURS" -p "$THEIRS" --exclusive -e "<patch>" -e "<patch>"
```

- **Pass each bundle as its own argument.** zsh doesn't split an unquoted variable into words; use bash, or separate
  arguments as above.
- **Pick the patches.** `--exclusive -e "<name>"` applies only the named patches. Include at least one patch that
  looks something up in the extension before changing anything and one that only injects calls into it. Morphe's
  bundle had no patches for the repo's apps on 2026-11-17, so no names clash; if that changes, list both bundles'
  patches for the app and pick names only the repo's bundle has.
- **The keystore** is a throwaway at `$H/ks.keystore`; these APKs are never installed. Delete the outputs and the
  CLI's temporary files with the run directory.

Judge a run by its result file and log, not its exit status: `"success":true`, empty `failedPatches`, every chosen
patch in `appliedPatches`, no `SEVERE` line. Expected: both orders pass. A failure in one order only is a shadowing
bug: check section 3's list again.

## 5. The shadowing run

Both orders passing shows that today's Morphe bundle doesn't shadow what the chosen patches read. It doesn't show that
the repo's patches would fail cleanly if a future bundle did. Test that: put a fake bundle first that holds some other
dex at the repo's own extension path. Build it with Python, from a script kept outside any download directory:

```bash
python3 -I - "$OURS" "$H/fake.mpp" "<our .mpe path>" "<another app's .mpe path in our bundle>" <<'EOF'
import sys, zipfile
dex = zipfile.ZipFile(sys.argv[1]).read(sys.argv[4])
with zipfile.ZipFile(sys.argv[2], "w") as z:
    z.writestr(sys.argv[3], dex)
EOF
run shadowed -p "$H/fake.mpp" -p "$OURS" --exclusive -e "<a patch that only injects calls>"
```

Our own bundle has an extension per app, so the other app's `.mpe` serves as the wrong dex. Whether the CLI accepts
an unsigned bundle with no patches at all wasn't tried; if it refuses it, say so and skip this run.

Expected: `failedPatches` names the patch, with the repo's own message that its extension added no classes. A run
that succeeds here is a bug to report, even though nothing failed: the APK would call classes it doesn't have.

## 6. What these checks don't cover

- Manager's UI: adding a source from a file or URL, the source card, the app chooser.
- Whether Manager loads sources through one class loader, and in what order.
- Manager's own Patcher and its JVM, its signing with an imported keystore, `adb install -r`, and whether the patched
  app works.

For those, run Manager on the device ([manager.md](manager.md)) and check the output
([apk-provenance.md](apk-provenance.md)).
