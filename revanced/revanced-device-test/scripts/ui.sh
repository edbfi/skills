#!/usr/bin/env bash
# ui.sh: drive an Android app's UI over adb by the text it shows, for ReVanced Manager runs.
#
# Every command except `nodes` talks to the device named by ANDROID_SERIAL, which adb reads
# itself. The node table has one tab-separated row per node that has a label:
#
#   bounds  cx  cy  clickable  checked  label
#
# bounds is uiautomator's "[x1,y1][x2,y2]", (cx, cy) its centre, and label the node's text, or
# its content-desc when the text is empty, with tabs and line breaks turned into spaces. A regex
# is a Python `re` pattern, matched with re.search against the label. Compose checkboxes and
# switches often have no node of their own, so `checked` can stay false while the screen shows a
# tick: read state from a screenshot or from a count the app prints.
#
# UI_OUT, when set, is an existing directory: each dump is kept there as ui.xml, and `shot`
# writes its PNGs there. Without it, dumps go to a temporary file and `shot` refuses.
#
# Exit codes: 0 ok, 1 no node matched (tap), 2 usage or environment error, 3 adb or
# uiautomator failure (no usable dump after retries, empty screenshot), 124 wait timed out.
set -euo pipefail

DEVICE_XML=/sdcard/ui.xml

usage() {
  cat <<'EOF'
usage: ui.sh <command> [args]

  dump [regex]            take a fresh dump; print its node table, or only matching rows
  nodes <file.xml> [regex]
                          print the node table of a saved dump (no device needed)
  tap <regex> [nth]       tap the centre of the nth matching node (default 1)
  wait <regex> [secs]     dump until a node matches, then print its rows (default 30 s)
  shot <name>             save a screenshot as $UI_OUT/<name>.png
  type <text>             type text into the focused field (spaces become %s)
EOF
}

die() { printf 'ui.sh: %s\n' "$2" >&2; exit "$1"; }

# Print the node table of dump $1, filtered by regex $2 when it is given.
# Exits 3 when the file isn't a uiautomator dump with nodes, 2 on a bad regex.
table() {
  python3 -I -c '
import re, sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
try:
    pattern = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
except re.error as error:
    sys.exit(f"ui.sh: bad regex {sys.argv[2]!r}: {error}")
try:
    root = ET.parse(path).getroot()
except (ET.ParseError, OSError) as error:
    print(f"ui.sh: {path} is not a uiautomator dump: {error}", file=sys.stderr)
    sys.exit(3)
if root.tag != "hierarchy" or root.find(".//node") is None:
    print(f"ui.sh: {path} holds no UI nodes", file=sys.stderr)
    sys.exit(3)
corners = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
for node in root.iter("node"):
    label = " ".join((node.get("text") or node.get("content-desc") or "").split())
    if not label or (pattern and not pattern.search(label)):
        continue
    bounds = node.get("bounds", "")
    match = corners.fullmatch(bounds)
    if not match:
        print(f"ui.sh: skipping {label!r}: unreadable bounds {bounds!r}", file=sys.stderr)
        continue
    x1, y1, x2, y2 = map(int, match.groups())
    print(bounds, (x1 + x2) // 2, (y1 + y2) // 2, node.get("clickable"), node.get("checked"), label, sep="\t")
' "$@" || {
    local status=$?
    [[ $status -eq 1 ]] && exit 2 # sys.exit(message) above: a bad regex
    exit "$status"
  }
}

need_device() {
  [[ -n ${ANDROID_SERIAL:-} ]] || die 2 "set ANDROID_SERIAL to the test device's serial"
  command -v adb >/dev/null || die 2 "adb isn't on PATH"
}

xml_file() {
  if [[ -n ${UI_OUT:-} ]]; then
    [[ -d $UI_OUT ]] || die 2 "UI_OUT=$UI_OUT is not a directory"
    xml=$UI_OUT/ui.xml
  else
    xml=$(mktemp)
    trap 'rm -f "$xml"' EXIT
  fi
}

# Take a fresh dump into $xml. The device file is removed first so a failed dump can't leave the
# previous screen behind; an empty or unparsable dump is retried.
dump_xml() {
  local try
  for try in 1 2 3; do
    adb shell rm -f "$DEVICE_XML" >/dev/null 2>&1 || true
    if adb shell uiautomator dump "$DEVICE_XML" >/dev/null 2>&1 &&
      adb exec-out cat "$DEVICE_XML" >"$xml" 2>/dev/null &&
      (table "$xml" >/dev/null 2>&1); then
      return 0
    fi
    sleep 1
  done
  die 3 "no usable uiautomator dump after $try tries; is the screen on and the app idle?"
}

positive_int() { [[ $1 =~ ^[1-9][0-9]*$ ]] || die 2 "$2 must be a positive integer, not '$1'"; }

command=${1:-}
[[ -n $command ]] || {
  usage >&2
  exit 2
}
shift

case $command in
  dump)
    [[ $# -le 1 ]] || die 2 "usage: ui.sh dump [regex]"
    need_device
    xml_file
    dump_xml
    table "$xml" "$@"
    ;;
  nodes)
    [[ $# -ge 1 && $# -le 2 ]] || die 2 "usage: ui.sh nodes <file.xml> [regex]"
    [[ -f $1 ]] || die 2 "no such file: $1"
    table "$@"
    ;;
  tap)
    [[ $# -ge 1 && $# -le 2 ]] || die 2 "usage: ui.sh tap <regex> [nth]"
    nth=${2:-1}
    positive_int "$nth" nth
    need_device
    xml_file
    dump_xml
    row=$(table "$xml" "$1" | sed -n "${nth}p")
    [[ -n $row ]] || die 1 "no node matches /$1/ (match $nth)"
    IFS=$'\t' read -r bounds cx cy _ <<<"$row"
    adb shell input tap "$cx" "$cy"
    printf 'tapped /%s/ at %s\n' "$1" "$bounds"
    ;;
  wait)
    [[ $# -ge 1 && $# -le 2 ]] || die 2 "usage: ui.sh wait <regex> [secs]"
    secs=${2:-30}
    positive_int "$secs" secs
    need_device
    xml_file
    deadline=$((SECONDS + secs))
    while :; do
      dump_xml
      rows=$(table "$xml" "$1")
      if [[ -n $rows ]]; then
        printf '%s\n' "$rows"
        exit 0
      fi
      ((SECONDS <= deadline)) || die 124 "timed out after ${secs}s waiting for /$1/"
      sleep 1
    done
    ;;
  shot)
    [[ $# -eq 1 ]] || die 2 "usage: ui.sh shot <name>"
    [[ $1 =~ ^[A-Za-z0-9._-]+$ ]] || die 2 "a shot name is letters, digits, '.', '_' and '-' only"
    [[ -n ${UI_OUT:-} && -d $UI_OUT ]] || die 2 "set UI_OUT to the directory that keeps this run's screenshots"
    need_device
    png=$UI_OUT/$1.png
    adb exec-out screencap -p >"$png"
    [[ -s $png ]] || die 3 "screencap wrote nothing to $png"
    printf '%s\n' "$png"
    ;;
  type)
    [[ $# -eq 1 && -n $1 ]] || die 2 "usage: ui.sh type <text>"
    # `input text` takes %s for a space; the device shell gets the text in single quotes.
    [[ $1 != *[\'%]* ]] || die 2 "type can't send ' or %"
    need_device
    adb shell input text "'${1// /%s}'"
    ;;
  -h | --help | help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
