# Host checks: two bundles in the CLI

Checks that run on the host with revanced-cli, without the device, and catch the class of bug Manager exposed on
2026-11-09: a bundle that only works when it is the only one loaded. Run them before the Manager part of the
workflow, and again whenever ReVanced's bundle, the CLI or the repo's extensions change. They take minutes; the same
bug through Manager takes a device and a coin flip ([manager.md](manager.md) section 10).

## Contents

1. Why a second bundle matters
2. Get ReVanced's bundle
3. List a bundle's patches for an app
4. Two bundles, both orders
5. The shadowing run
6. What these checks don't cover

## 1. Why a second bundle matters

Patcher loads every bundle passed to it through one class loader, in the CLI as in Manager, and a patch reads its
extension through that loader. A file at the same path in two bundles comes from whichever bundle is first. The
repo's patch recipe passes one bundle (see its `justfile`), so it can never see this.

On 2026-11-09, ReVanced's bundle shipped `extensions/syncforreddit.rve`, the same path as edbfi/revanced-patches
v0.1.0's extension. With ReVanced's bundle first, the CLI failed "Enable Sync Ultra" with `Could not find
WebsitePreviews.isEnabled in the extension`, then wrote the APK and exited 0. With the repo's bundle first it
succeeded. PR #21 gave the repo's extension a path of its own and made the extension patch fail when none of its
classes arrive.

## 2. Get ReVanced's bundle

Use the release Manager loads (its Patches tab shows the version, v6.2.1 on 2026-11-09). GitHub answers
`ReVanced/revanced-patches` with HTTP 451; ReVanced's API serves the bundle:

```bash
R=$TMP/revanced-patches-bundle; mkdir -p "$R"
curl -fsS https://api.revanced.app/v5/patches -o "$R/release.json"
jq -r '.version, .download_url' "$R/release.json"
curl -fsSL -o "$R/revanced.rvp" "$(jq -r .download_url "$R/release.json")"
sha256sum "$R/revanced.rvp"
```

On 2026-11-09 this gave `v6.2.1`, `download_url` `https://api.revanced.app/v5/patches.rvp`, and SHA-256
`50f41e4656b7374a1c8fe5579fd107f697f86d7f13fc6cd194cf3821761dc4b4`; the release notes linked ReVanced's repository
on GitLab. `https://api.revanced.app/v5/patches/list` answered 403. Record the version and SHA-256 in the report. The
bundle runs only in these host checks, with `-b` (no signature check): never install an APK patched with it.

## 3. List a bundle's patches for an app

```bash
java -jar "$CLI" list-patches -b -p "$R/revanced.rvp" --packages --filter-package-name <package> |
  grep -E 'Name:|Enabled:' | paste - -
```

`$CLI` is the CLI jar the repo's patch recipe fetches and pins (see its `justfile`). Each line is `Name: <patch>`,
`Enabled: true|false`; `Enabled: true` patches are the ones Manager selects by default. The filter keeps patches made
for any app too. On 2026-11-09 ReVanced's v6.2.1 had seven default-on patches for Sync for Reddit, and seven of its
Sync patch names were also in the repo's bundle. Run the same command on the repo's bundle and compare the names:
same-named patches are the ones whose order decides a mixed run ([manager.md](manager.md) section 11).

## 4. Two bundles, both orders

```bash
H=$TMP/host-checks; mkdir -p "$H"
OURS=<the repo's built bundle>.rvp
THEIRS=$R/revanced.rvp
APK=<the checked original APK>
run() {
  local name=$1; shift
  java -jar "$CLI" patch "$@" --keystore "$H/ks.keystore" -o "$H/$name.apk" "$APK" > "$H/$name.log" 2>&1
  echo "== $name exit=$?"
  grep -E 'SEVERE|succeeded|failed|Could not find|Saved' "$H/$name.log"
}
run theirs-first -p "$THEIRS" -b -p "$OURS" -b --exclusive -e "<patch>" -e "<patch>"
run ours-first -p "$OURS" -b -p "$THEIRS" -b --exclusive -e "<patch>" -e "<patch>"
```

- **`-b` belongs to each `-p`.** Without it the CLI stops with `Missing required argument(s): (-b | [-s=<signatureFile>
  -k=<publicKeyRingFile> -a=<attestationFile> ([-r=<repository>])])`.
- **Pass each bundle as its own argument.** The run first kept the `-p … -b` flags in one unquoted variable; zsh
  doesn't split it into words, and the CLI reported `Patches file  … -p … does not exist`. Use bash, or separate
  arguments as above.
- **On arm64 Linux** set up the CLI's x86_64 aapt2 the way the repo's patch recipe does before calling `java`.
- **Pick the patches.** `--exclusive -e "<name>"` applies only the named patches. Choose names only the repo's bundle
  has (section 3), so ReVanced's same-named patches don't join the run, and include at least one patch that looks
  something up in the extension before changing anything and one that only injects calls into it. On 2026-11-09 the
  first reproduction used only "Enable Sync Ultra"; the PR #21 check used Enable Sync Ultra, Fix Tenor previews, Fix
  Other discussions and Fix galleries.
- **The keystore** is a throwaway the CLI creates at `$H/ks.keystore`; these APKs are never installed. The CLI also
  leaves `<name>-temporary-files` next to each output; delete them with the outputs.

**The CLI exits 0 and writes the APK even when a patch fails.** Judge a run by its log, not its exit status:

```bash
grep -n '^SEVERE' "$H/theirs-first.log" && echo "theirs-first failed"
```

Expected: both orders succeed. A failure only with ReVanced's bundle first is this bug; check which file of the repo's
bundle shares a path with ReVanced's:

```bash
unzip -l "$THEIRS" | grep -E 'extensions/'
unzip -l "$OURS" | grep -vE '<repo class prefix>/.*\.class$'
```

The patches repo's `AGENTS.md` names the prefixes its bundle files must use, and its tests check them.

## 5. The shadowing run

Both orders passing shows that today's ReVanced bundle doesn't shadow what the chosen patches read. It doesn't show
that the repo's patches would fail cleanly if a future bundle shadowed the extension. Test that: put a fake bundle
first that holds some other extension dex at the repo's own extension path.

`zip` wasn't installed on the run's host, so the fake bundle is built with Python, from a script kept outside the
download directory:

```bash
python3 -I - "$THEIRS" "$H/fake.rvp" "<their .rve path>" "<our .rve path>" <<'EOF'
import sys, zipfile
rve = zipfile.ZipFile(sys.argv[1]).read(sys.argv[3])
with zipfile.ZipFile(sys.argv[2], "w") as z:
    z.writestr(sys.argv[4], rve)
EOF
run shadowed -p "$H/fake.rvp" -b -p "$OURS" -b --exclusive -e "<a patch that only injects calls>"
```

`<our .rve path>` is the path the repo's `AGENTS.md` gives for the app's extension. If ReVanced's bundle has no
extension for the app, use any of its `.rve` files.

Expected: `SEVERE: "<patch>" failed:` with the repo's own message that its extension added no classes. On 2026-11-09,
after PR #21: `PatchException: extensions/edbfi/syncforreddit.rve added no extension classes`, raised by the
extension patch the tested patch depends on. Before PR #21 the same kind of run (ReVanced's bundle first, "Fix Other
discussions" only) "succeeded" with ReVanced's extension merged in: an APK with calls into classes it doesn't have.
A run that succeeds here is a bug to report, even though nothing failed.

## 6. What these checks don't cover

- Manager's UI: bundle loading from a file or URL, the info page, the options screens.
- Manager's selection defaults: which of ReVanced's patches it adds, and the lock on changing them.
- The uid order Manager actually gives a bundle, and Manager's own Patcher and aapt2.
- Save APK, signing with an imported keystore, `adb install -r`, and whether the patched app works.

For those, run Manager on the device ([manager.md](manager.md)) and check the output
([apk-provenance.md](apk-provenance.md)).
