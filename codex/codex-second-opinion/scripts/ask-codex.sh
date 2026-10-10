#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Run one read-only Codex turn through the codex CLI. The prompt is read from stdin.
#
#   ask-codex.sh [--cwd DIR] [--model NAME] [--effort LEVEL] <<'EOF'
#   ask-codex.sh --resume RUN_DIR [--model NAME] [--effort LEVEL] <<'EOF'
#
# Without --model/--effort, Codex uses its own configured defaults
# (~/.codex/config.toml). A --resume follow-up reuses the model and effort that
# the earlier run actually used. Each call writes a fresh run directory holding
# prompt.md, answer.md, run.log and run.env, prints a summary block, then
# prints Codex's answer. Exit status: Codex's own exit status, 3 if Codex
# exited 0 with an empty answer, 2 for a usage error.
set -uo pipefail

model=
effort=
cwd=$PWD
resume=
session=

usage() { sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//' >&2; exit "${1:-2}"; }
die() { printf 'ask-codex: %s\n' "$1" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case $1 in
    --cwd) [ $# -ge 2 ] || usage; cwd=$2; shift 2 ;;
    --model) [ $# -ge 2 ] || usage; model=$2; shift 2 ;;
    --effort) [ $# -ge 2 ] || usage; effort=$2; shift 2 ;;
    --resume) [ $# -ge 2 ] || usage; resume=$2; shift 2 ;;
    -h|--help) usage 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[ -t 0 ] && die "pipe the prompt on stdin (use a quoted heredoc: <<'EOF')"
command -v codex > /dev/null || die "the codex CLI is not on PATH (npm install -g @openai/codex, then codex login)"

if [ -n "$resume" ]; then
  [ -f "$resume/run.env" ] || die "not a run directory: $resume"
  # A follow-up continues the same Codex session, from the same folder, on the
  # same model and effort unless the caller overrides them.
  cwd=$(sed -n 's/^CWD=//p' "$resume/run.env")
  session=$(sed -n 's/^SESSION=//p' "$resume/run.env")
  [ -n "$model" ] || model=$(sed -n 's/^MODEL=//p' "$resume/run.env")
  [ -n "$effort" ] || effort=$(sed -n 's/^EFFORT=//p' "$resume/run.env")
  [ -n "$session" ] || die "no Codex session id recorded in $resume/run.env"
fi

[ -d "$cwd" ] || die "no such directory: $cwd"
cwd=$(cd "$cwd" && pwd -P)

tmp=${TMPDIR:-/tmp}
run=$(mktemp -d "${tmp%/}/codex-second-opinion.XXXXXX") || die "cannot create a run directory"
cat > "$run/prompt.md"
[ -s "$run/prompt.md" ] || die "the prompt on stdin is empty"
: > "$run/answer.md"

# `command` skips any shell function or alias named codex. Sessions are kept
# (no --ephemeral) so a follow-up can resume them.
set -- -c sandbox_mode=read-only --skip-git-repo-check -o "$run/answer.md"
[ -n "$model" ] && set -- "$@" -m "$model"
[ -n "$effort" ] && set -- "$@" -c "model_reasoning_effort=$effort"
if [ -n "$resume" ]; then
  (cd "$cwd" && command codex exec resume "$@" "$session" -) < "$run/prompt.md" > "$run/run.log" 2>&1
else
  (cd "$cwd" && command codex exec -C "$cwd" "$@" -) < "$run/prompt.md" > "$run/run.log" 2>&1
fi
status=$?

# The log header states what actually ran, including values taken from config.
header() { sed -n "s/^$1:[[:space:]]*//p" "$run/run.log" | head -1; }
[ -n "$resume" ] || session=$(header 'session id')
used_model=$(header model)
used_effort=$(header 'reasoning effort')
model=${used_model:-$model}
effort=${used_effort:-$effort}

if [ "$status" = 0 ] && ! grep -q '[^[:space:]]' "$run/answer.md"; then
  status=3
fi

{
  printf 'CWD=%s\n' "$cwd"
  printf 'MODEL=%s\n' "$model"
  printf 'EFFORT=%s\n' "$effort"
  printf 'SESSION=%s\n' "$session"
  printf 'STATUS=%s\n' "$status"
} > "$run/run.env"

printf 'model:   %s (effort %s)\n' "${model:-unknown}" "${effort:-unknown}"
printf 'folder:  %s\n' "$cwd"
printf 'status:  %s\n' "$status"
printf 'run:     %s\n' "$run"
printf 'session: %s\n' "${session:-unknown}"
if [ "$status" = 0 ]; then
  printf '===== Codex answer (%s/answer.md) =====\n' "$run"
  cat "$run/answer.md"
  [ -n "$(tail -c 1 "$run/answer.md")" ] && printf '\n'
else
  printf '===== Codex FAILED; last 40 lines of %s/run.log =====\n' "$run"
  tail -n 40 "$run/run.log"
fi
exit "$status"
