#!/usr/bin/env bash
# readd-bundle.sh: delete a local patches bundle in ReVanced Manager and add the same .rvp again
# until Manager gives it a uid with the wanted sign.
#
# Manager hands every loaded bundle to one class loader in uid order, ascending, and its own
# ReVanced Patches bundle is uid 0. A positive uid puts the bundle after ReVanced's, a negative one
# before it. Each add draws a new random uid, so every try is a coin flip. (Observed on 2026-11-09
# with Manager v2.6.0; see references/manager.md.)
#
# Start with Manager in the foreground on its Patches tab, the bundle already added once from
# /sdcard/Download/<file>, and no other local bundle loaded. Each try enters edit mode (Manager
# leaves it after every add), taps the trash icon in the row that shows <display-name>, confirms,
# adds /sdcard/Download/<file> through Add patches -> Select from storage, and reads the new uid
# from logcat, which it clears before each add. A step whose screen or button doesn't show up
# stops the script: nothing is tapped blind.
#
# Environment:
#   ANDROID_SERIAL        the test device (required; adb and ui.sh read it)
#   UI_OUT                passed on to ui.sh (optional)
#   ADD_FAB_X, ADD_FAB_Y  where to tap the Add patches button, which uiautomator doesn't see
#
# Exit codes: 0 the uid has the wanted sign, 1 tries ran out, 2 usage or environment error,
# 3 a screen or tap target didn't show up, 4 logcat held no single new local bundle uid.
set -euo pipefail
# readd runs in a command substitution; without this, a failed step inside it wouldn't stop it.
shopt -s inherit_errexit

# The Add patches button, measured on 2026-11-09 with Manager v2.6.0 on a 1080x2400, 420 dpi
# screen (the size and density the patches repo's device recipe gave Redroid). Re-measure from a
# screenshot when Manager or the screen changes, and pass the result in ADD_FAB_X and ADD_FAB_Y.
MEASURED_SIZE=1080x2400
DEFAULT_FAB_X=840
DEFAULT_FAB_Y=2158

PACKAGE=app.revanced.manager.flutter
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
UI=$here/ui.sh

usage() {
  cat <<'EOF'
usage: readd-bundle.sh <display-name> <file> <positive|negative> [max-tries]

  display-name  the bundle's name as Manager's Patches tab shows it
  file          the .rvp's name in /sdcard/Download
  positive      ReVanced's bundle loads first (the order a positive uid gives)
  negative      this bundle loads first
  max-tries     default 6

Exit codes: 0 the uid has the wanted sign, 1 tries ran out, 2 usage or environment error,
3 a screen or tap target didn't show up, 4 the new uid couldn't be read from logcat.
EOF
}

die() { printf 'readd-bundle: %s\n' "${*:2}" >&2; exit "$1"; }

case ${1:-} in -h | --help) usage; exit 0 ;; esac
[[ $# -ge 3 && $# -le 4 ]] || {
  usage >&2
  exit 2
}
name=$1 file=$2 sign=$3 max=${4:-6}
[[ -n $name ]] || die 2 "the display name is empty"
[[ $file =~ ^[A-Za-z0-9._-]+\.rvp$ ]] || die 2 "file must be a plain .rvp file name (letters, digits, . _ -)"
[[ $sign == positive || $sign == negative ]] || die 2 "the sign is positive or negative, not '$sign'"
[[ $max =~ ^[1-9][0-9]*$ ]] || die 2 "max-tries must be a positive integer"
[[ -n ${ANDROID_SERIAL:-} ]] || die 2 "set ANDROID_SERIAL to the test device's serial"
command -v adb >/dev/null || die 2 "adb isn't on PATH"

# The fixed coordinates only fit the screen they were measured on.
size=$(adb shell wm size | tr -d '\r' | sed -n 's/^Override size: //p; s/^Physical size: //p' | tail -n 1)
fab_x=${ADD_FAB_X:-$DEFAULT_FAB_X}
fab_y=${ADD_FAB_Y:-$DEFAULT_FAB_Y}
[[ $fab_x =~ ^[0-9]+$ && $fab_y =~ ^[0-9]+$ ]] || die 2 "ADD_FAB_X and ADD_FAB_Y must be whole numbers"
# On another screen both coordinates must be measured: one default plus one override is a blind tap.
if [[ $size != "$MEASURED_SIZE" && (-z ${ADD_FAB_X:-} || -z ${ADD_FAB_Y:-}) ]]; then
  die 2 "the screen is ${size:-unknown}, not $MEASURED_SIZE: measure the Add patches button," \
    "then set both ADD_FAB_X and ADD_FAB_Y"
fi

focus=$(adb shell dumpsys window | grep mCurrentFocus || true)
[[ $focus == *"$PACKAGE/"* ]] || die 3 "Manager isn't in the foreground; open it on the Patches tab first"
adb shell ls "/sdcard/Download/$file" >/dev/null 2>&1 || die 2 "/sdcard/Download/$file isn't on the device"

# The file name as a Python regex that matches only itself.
# shellcheck disable=SC2001 # a bracket class reads better in sed than in ${//}
file_re="^$(printf '%s' "$file" | sed 's/[.]/\\./g')\$"

# Tap a node, or stop: a missing node means the screen isn't the one this script expects.
tap() { "$UI" tap "$@" >/dev/null || die 3 "no '$1' on screen"; }
await() { "$UI" wait "$1" "${2:-15}" >/dev/null || die 3 "'$1' didn't show up within ${2:-15}s"; }

# Print "cx cy" of the trash icon in the bundle's row, or nothing outside edit mode. The icon is
# the "Delete" node whose centre lies in the band of the name line and the subtitle under it.
# Rows reorder with the uid, and the dump doesn't list them in screen order, so the row is found
# by name, never by position.
trash_of_row() {
  local table rows y1 y2
  table=$("$UI" dump)
  rows=$(NAME=$name awk -F'\t' '$6 == ENVIRON["NAME"]' <<<"$table")
  [[ -n $rows ]] || die 3 "no row shows '$name' on the Patches tab"
  [[ $(wc -l <<<"$rows") -eq 1 ]] || die 3 "more than one row shows '$name'"
  [[ $rows =~ ^\[[0-9]+,([0-9]+)\]\[[0-9]+,([0-9]+)\] ]] || die 3 "can't read the bounds of '$name'"
  y1=${BASH_REMATCH[1]} y2=${BASH_REMATCH[2]}
  awk -F'\t' -v lo="$y1" -v hi="$((2 * y2 - y1))" '$6 == "Delete" && $3 >= lo && $3 <= hi { print $2, $3 }' <<<"$table"
}

# Delete the bundle, add the file again and print the new bundle's uid.
readd() {
  local trash i uids
  trash=$(trash_of_row)
  if [[ -z $trash ]]; then
    tap '^Edit$'
    for i in 1 2 3 4 5; do
      trash=$(trash_of_row)
      [[ -n $trash ]] && break
      sleep 1
    done
    [[ -n $trash ]] || die 3 "edit mode shows no trash icon in the row of '$name'"
  fi
  # shellcheck disable=SC2086 # "cx cy" splits into the two coordinates
  adb shell input tap $trash
  await 'will be deleted$'
  # NAME is set on awk, the command that reads it: a prefix on the pipeline's first command stops there.
  "$UI" dump 'will be deleted$' |
    NAME=$name awk -F'\t' 'index($6, ENVIRON["NAME"]) { found = 1 } END { exit !found }' ||
    die 3 "the delete dialog doesn't name '$name'; tap Cancel and check the screen"
  tap '^Confirm$'
  for i in $(seq 11); do
    "$UI" dump | NAME=$name awk -F'\t' '$6 == ENVIRON["NAME"] { found = 1 } END { exit found }' && break
    ((i < 11)) || die 3 "'$name' is still listed 10s after Confirm"
    sleep 1
  done

  # Still in edit mode: the button at the bottom right is Add patches.
  adb shell input tap "$fab_x" "$fab_y"
  "$UI" wait '^Select from storage$' 10 >/dev/null ||
    die 3 "tapping $fab_x,$fab_y didn't open Add patches; measure the button and set ADD_FAB_X and ADD_FAB_Y"
  tap '^Select from storage$'
  tap '^Next$'
  await '^Not selected$'
  tap '^Not selected$'

  # The system file picker opens on Recent the first time and in Downloads after that.
  if ! "$UI" wait "$file_re" 5 >/dev/null 2>&1; then
    tap '^Show roots$'
    await '^Downloads$'
    tap '^Downloads$'
    await "$file_re"
  fi
  # The file's name, not its "Preview the file ..." icon, which opens a preview.
  tap "$file_re"
  await '^Selected$'
  adb logcat -c
  tap '^Add$'

  # Manager logs a "Source: PatchBundleEntity(...)" line for every bundle once the new one loads.
  for i in $(seq 30); do
    uids=$(adb logcat -d |
      grep -oE 'PatchBundleEntity\(uid=-?[0-9]+, name=[^,]*, versionHash=null, source=local' |
      grep -oE 'uid=-?[0-9]+' | sort -u || true)
    [[ -n $uids ]] && break
    sleep 1
  done
  [[ -n $uids ]] || die 4 "no local bundle uid in logcat within 30s"
  [[ $(wc -l <<<"$uids") -eq 1 ]] ||
    die 4 "more than one local bundle in logcat ($(paste -sd' ' <<<"$uids")); remove the others first"
  await "^$(printf '%s' "$name" | sed 's/[][\\.^$*+?(){}|]/\\&/g')\$"
  printf '%s\n' "${uids#uid=}"
}

for try in $(seq "$max"); do
  uid=$(readd)
  [[ $uid =~ ^-?[0-9]+$ && $uid != 0 ]] || die 4 "read an unexpected uid '$uid'"
  printf 'try %d: uid=%s\n' "$try" "$uid"
  case $sign in
    positive) ((uid > 0)) && exit 0 ;;
    negative) ((uid < 0)) && exit 0 ;;
  esac
done
printf 'readd-bundle: no %s uid after %d tries\n' "$sign" "$max" >&2
exit 1
