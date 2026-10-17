#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Share one agent-browser browser between every docs-scout agent on this machine.
#
#   ab-host.sh new                     print a fresh session name (docsearch-<8 hex>)
#   ab-host.sh ab <session> <args...>  run one agent-browser command in that session, attached to
#                                      the shared browser (launched on first use)
#   ab-host.sh release <session>       close that session's tab and detach it, then run `down`
#   ab-host.sh up                      print the shared browser's CDP URL, launching it if needed
#   ab-host.sh down                    close the shared browser unless another docsearch-* session
#                                      still uses it
#
# The host session (docsearch-host) owns the only browser; nobody browses through it. Each agent
# attaches its own session over CDP with a pinned tab, so a seat-licensed executablePath such as
# CloakBrowser uses one seat however many agents run. agent-browser applies --idle-timeout from
# every command it receives (a command without it falls back to the 1 h default), so every host
# command here passes it. `ab` runs `up` first, which keeps the host alive while agents work and
# always attaches to the current CDP URL, even after the browser restarted.
#
# Closing the host must not race an agent that is attaching: `session list` shows a session only
# once its first command runs. So `ab` records an attach marker and fetches the CDP URL, and `down`
# checks sessions and fresh markers and closes the host, each under one lock. Python's fcntl takes
# the lock because flock(1) is missing on macOS. The lock fd is not inherited, so a browser
# daemon launched inside the lock never holds it.
#
# Exit status: the agent-browser command's own status for `ab`; otherwise 0 ok, 76 the browser
# could not start because its licence seat is taken (after two retries 30 s apart), 1 any other
# agent-browser failure, 2 usage.
set -uo pipefail

HOST=docsearch-host
HOST_IDLE=${DOCS_SCOUT_HOST_IDLE:-20m}
AGENT_IDLE=${DOCS_SCOUT_AGENT_IDLE:-10m}
SEAT_WAIT=${DOCS_SCOUT_SEAT_WAIT:-30}
SEAT_RE='exit code: 76|licen[cs]e|seat|session limit|concurrent session'

RUN_DIR="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/docs-scout-$(id -u)"
MARKER_MINUTES=2   # an attach marker this fresh counts as an attached agent

host() { agent-browser --idle-timeout "$HOST_IDLE" --session "$HOST" "$@"; }

# Run a command while holding the host lock (released when the command exits or dies).
locked() {
  mkdir -m 700 "$RUN_DIR" 2>/dev/null
  if [[ -L $RUN_DIR || ! -d $RUN_DIR || ! -O $RUN_DIR ]]; then
    printf 'ab-host: %s must be a directory you own\n' "$RUN_DIR" >&2
    return 1
  fi
  python3 -c 'import fcntl, os, subprocess, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
sys.exit(subprocess.run(sys.argv[2:]).returncode)' "$RUN_DIR/host.lock" "$@"
}

# Sessions still using the host: listed ones plus agents that attached in the last few minutes.
attached_others() {
  local markers
  find "$RUN_DIR" -maxdepth 1 -name 'attach-docsearch-*' -mmin +"$MARKER_MINUTES" -exec rm -f {} + 2>/dev/null
  markers=$(find "$RUN_DIR" -maxdepth 1 -name 'attach-docsearch-*' 2>/dev/null | sed 's|.*/attach-||')
  { sessions; printf '%s\n' "$markers"; } | grep -v -e '^$' -e "^$HOST\$" | sort -u
}

sessions() { agent-browser session list 2>/dev/null | sed -n 's/^  *\(docsearch-[A-Za-z0-9_-]*\)$/\1/p'; }

# A launch that fails can leave the session's daemon running; close it, then stop what is left.
reap_host() {
  agent-browser --session "$HOST" close >/dev/null 2>&1
  sleep 2
  sessions | grep -qx "$HOST" || return 0
  local pid
  pid=$(agent-browser --json --session "$HOST" session info 2>/dev/null |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["data"].get("pid") or "")' 2>/dev/null)
  [[ $pid =~ ^[0-9]+$ ]] && kill "$pid" 2>/dev/null
  return 0
}

cmd_up() {
  local attempt out rc
  for attempt in 1 2 3; do
    out=$(host get cdp-url 2>&1)
    rc=$?
    if [[ $rc -eq 0 && $out == ws://* ]]; then
      printf '%s\n' "$out"
      return 0
    fi
    if ! grep -qiE "$SEAT_RE" <<<"$out"; then
      printf 'ab-host: could not start the host browser:\n%s\n' "$out" >&2
      reap_host
      return 1
    fi
    reap_host
    if [[ $attempt -lt 3 ]]; then
      printf 'ab-host: browser seat busy, retrying in %ss (%s/2)\n' "$SEAT_WAIT" "$attempt" >&2
      sleep "$SEAT_WAIT"
    fi
  done
  printf 'ab-host: CloakBrowser seat busy; the web tier is unavailable right now\n' >&2
  return 76
}

cmd_new() {
  printf 'docsearch-%s\n' "$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
}

valid_name() {
  [[ ${1:-} =~ ^docsearch-[0-9a-f]{8}(-[A-Za-z0-9]+)?$ ]] && return 0
  printf 'ab-host: expected a session name from "ab-host.sh new", got %q\n' "${1:-}" >&2
  return 2
}

cmd_ab() {
  local name=${1:-} url
  valid_name "$name" || return
  shift
  url=$(locked bash "$0" _attach "$name") || return
  exec agent-browser --session "$name" --idle-timeout "$AGENT_IDLE" --cdp "$url" "$@"
}

# Inside the lock: mark the session as attaching, then make sure the host is up.
attach_locked() {
  touch "$RUN_DIR/attach-$1" && cmd_up
}

# Detaching occasionally leaves the session's daemon listed, so check and close once more.
cmd_release() {
  local name=${1:-} url attempt
  valid_name "$name" || return
  rm -f "$RUN_DIR/attach-$name"
  if sessions | grep -qx "$HOST"; then
    url=$(host get cdp-url 2>/dev/null)
    if [[ $url == ws://* ]]; then
      agent-browser --session "$name" --idle-timeout "$AGENT_IDLE" --cdp "$url" tab close >/dev/null 2>&1
    fi
  fi
  for attempt in 1 2 3; do
    sessions | grep -qx "$name" || break
    agent-browser --session "$name" close >/dev/null 2>&1
    sleep "$attempt"
  done
  if sessions | grep -qx "$name"; then
    printf 'ab-host: %s is still listed; it expires after %s idle\n' "$name" "$AGENT_IDLE" >&2
  else
    printf 'ab-host: released %s\n' "$name" >&2
  fi
  cmd_down
}

cmd_down() {
  locked bash "$0" _down
}

down_locked() {
  local others
  others=$(attached_others)
  if [[ -n $others ]]; then
    printf 'ab-host: shared browser kept; still attached: %s\n' "$(tr '\n' ' ' <<<"$others")" >&2
    return 0
  fi
  if sessions | grep -qx "$HOST"; then
    host close >/dev/null 2>&1
    printf 'ab-host: shared browser closed\n' >&2
  fi
  return 0
}

case ${1:-} in
  up) cmd_up ;;
  new) cmd_new ;;
  ab) shift; cmd_ab "$@" ;;
  release) shift; cmd_release "$@" ;;
  down) cmd_down ;;
  _attach) valid_name "${2:-}" && attach_locked "$2" ;;
  _down) down_locked ;;
  *)
    sed -n '3,11p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
