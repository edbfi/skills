#!/usr/bin/env bash
# checklist-gaps.sh: compare a patches repo's app page with this skill's per-app checklist.
#
# The patch names come from the first column of the docs' Patches table: the table under the `## Patches` heading
# whose header row is `| Patch | What it does | Default |` (cell padding is ignored). The checklist's entries are
# the `### ` headings under its own `## Patches` heading. Names must match exactly. Fenced code blocks are skipped
# in both files.
#
# Prints the patches with no checklist entry, the entries for patches the docs no longer list, duplicate entries,
# and the entries holding `unverified: confirm on the next run` (informational: they don't change the exit code).
# A missing checklist file means a new app: every patch is reported as missing an entry.
#
# Exit codes: 0 no missing, stale or duplicate entries, 1 there are some, 2 usage or parse error (no Patches
# section or table in the docs, an empty table, a duplicate patch name in the docs, a checklist with no
# `## Patches` section). A parse error never reports "no gaps".
set -euo pipefail

UNVERIFIED='unverified: confirm on the next run'

usage() {
  cat <<'EOF'
usage: checklist-gaps.sh <docs/app.md> <references/apps/app.md>

  <docs/app.md>               the app's page in the patches repo, e.g. docs/syncforreddit.md
                              (or a copy from `git show origin/main:docs/<app>.md`)
  <references/apps/app.md>    this skill's checklist for the app; may not exist yet

Exit codes: 0 no gaps, 1 gaps found, 2 usage or parse error.
EOF
}

die() { printf 'checklist-gaps: %s\n' "$*" >&2; exit 2; }

case ${1:-} in -h | --help) usage; exit 0 ;; esac
[[ $# -eq 2 ]] || { usage >&2; exit 2; }
docs=$1
checklist=$2
[[ -f $docs && -r $docs ]] || die "cannot read the docs page: $docs"

export LC_ALL=C
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# Patch names from the docs' Patches table, one per line. awk exits 3 when the section, the header row or its
# separator is missing, 4 when the table has no rows and 5 when a row has no name.
docs_status=0
awk '
  { sub(/\r$/, "") }
  /^ ? ? ?(```|~~~)/ { fenced = !fenced; next }
  fenced { next }
  /^##?[ \t]/ {
    if (in_section) exit
    if ($0 ~ /^##[ \t]+Patches[ \t]*$/) in_section = 1
    next
  }
  !in_section { next }
  state == 0 && /^[ \t]*\|[ \t]*Patch[ \t]*\|[ \t]*What it does[ \t]*\|[ \t]*Default[ \t]*\|[ \t]*$/ { state = 1; next }
  state == 1 {
    if ($0 !~ /^[ \t]*\|[ \t:|-]+\|[ \t]*$/) { err = 3; exit }
    state = 2
    next
  }
  state == 2 {
    if ($0 !~ /^[ \t]*\|/) exit
    row = $0
    sub(/^[ \t]*\|/, "", row)
    cell = row
    sub(/\|.*$/, "", cell)
    gsub(/^[ \t]+|[ \t]+$/, "", cell)
    if (cell == "") { err = 5; exit }
    print cell
    rows++
  }
  END {
    if (err) exit err
    if (!in_section || state == 0) exit 3
    if (rows == 0) exit 4
  }
' "$docs" > "$work/docs.raw" || docs_status=$?
case $docs_status in
  0) ;;
  3) die "no Patches table under '## Patches' with the header '| Patch | What it does | Default |' in $docs" ;;
  4) die "the Patches table in $docs has no rows" ;;
  5) die "a row of the Patches table in $docs has an empty Patch cell" ;;
  *) die "could not read $docs (awk exit $docs_status)" ;;
esac
dups=$(sort "$work/docs.raw" | uniq -d)
[[ -z $dups ]] || die "duplicate patch names in $docs: $(paste -sd ',' - <<<"$dups")"
sort "$work/docs.raw" > "$work/docs.sorted"

# Checklist entries: "### " headings under "## Patches", and which of them hold the unverified marker.
: > "$work/entries.raw"
: > "$work/unverified.raw"
missing_file=0
if [[ ! -e $checklist ]]; then
  missing_file=1
else
  [[ -f $checklist && -r $checklist ]] || die "cannot read the checklist: $checklist"
  list_status=0
  awk -v marker="$UNVERIFIED" -v entries="$work/entries.raw" -v unverified="$work/unverified.raw" '
    { sub(/\r$/, "") }
    /^ ? ? ?(```|~~~)/ { fenced = !fenced }
    !fenced && /^##?[ \t]/ {
      if (in_section) { in_section = 0; entry = ""; done = 1 }
      if (!done && $0 ~ /^##[ \t]+Patches[ \t]*$/) { in_section = 1; seen = 1 }
      next
    }
    !in_section { next }
    !fenced && /^###[ \t]/ {
      entry = $0
      sub(/^###[ \t]+/, "", entry)
      sub(/[ \t]+#*[ \t]*$/, "", entry)
      print entry > entries
      next
    }
    entry != "" && index($0, marker) && !(entry in flagged) { flagged[entry] = 1; print entry > unverified }
    END { if (!seen) exit 3 }
  ' "$checklist" || list_status=$?
  case $list_status in
    0) ;;
    3) die "no '## Patches' section in $checklist" ;;
    *) die "could not read $checklist (awk exit $list_status)" ;;
  esac
fi
sort -u "$work/entries.raw" > "$work/entries.sorted"
sort "$work/entries.raw" | uniq -d > "$work/entries.dups"

comm -23 "$work/docs.sorted" "$work/entries.sorted" > "$work/missing"
comm -13 "$work/docs.sorted" "$work/entries.sorted" > "$work/stale"

# List a file's lines in the docs' order where they are patch names, else sorted.
section() {
  local title=$1 file=$2
  printf '%s\n' "$title"
  if [[ ! -s $file ]]; then
    printf '  (none)\n'
    return
  fi
  local name
  while IFS= read -r name; do
    grep -qxF -- "$name" "$file" && printf '  - %s\n' "$name"
  done < "$work/docs.raw"
  while IFS= read -r name; do
    grep -qxF -- "$name" "$work/docs.raw" || printf '  - %s\n' "$name"
  done < <(sort -u "$file")
}

printf 'Docs: %s (%d patches)\n' "$docs" "$(wc -l < "$work/docs.sorted")"
if ((missing_file)); then
  printf 'Checklist: %s does not exist: every patch needs an entry\n\n' "$checklist"
else
  printf 'Checklist: %s (%d entries)\n\n' "$checklist" "$(wc -l < "$work/entries.raw")"
fi
section 'Patches with no checklist entry:' "$work/missing"
section 'Checklist entries for patches the docs no longer list:' "$work/stale"
section 'Duplicate checklist entries:' "$work/entries.dups"
section "Entries marked '$UNVERIFIED':" "$work/unverified.raw"

if [[ -s $work/missing || -s $work/stale || -s $work/entries.dups ]]; then
  exit 1
fi
exit 0
