# Keys, state and permissions

## Setup

```bash
python3 scripts/c7search.py init
```

`init` creates `${XDG_CONFIG_HOME:-~/.config}/docs-scout/` (mode 0700) and a template
`config.toml` (mode 0600, never overwritten; exit 73 if it already exists) and prints its path. The
user opens the file in an editor and pastes in the keys from the Context7 dashboard:

```toml
[[keys]]
label = "primary"
key = "<paste key>"

[[keys]]
label = "secondary"
key = "<paste key>"
```

Entries whose key is empty or still starts with `<` are ignored, so the template alone means "no
keys". An agent runs `init` only when the user asks it to set up keys. During a search it just
passes the fix from stderr on to the user. It never writes, echoes or exports a key itself and
never asks for one in the chat. `CONTEXT7_API_KEYS` (comma-separated) replaces the file when set,
which suits CI; those keys are labelled `env1`, `env2`, ...

## Permission check

Before reading the file the script checks it with `lstat`, so symlinks are not followed. It exits 78
with the fix to run unless all of these hold:

- `config.toml` is a regular file (not a symlink), owned by you, with no group or other permission
  bits (`chmod 600`).
- Its directory is a real directory owned by you and not group- or other-writable (`chmod 700`).

## Balancing two keys

The free tier gives each key 1,000 requests a month. For every request the script picks the usable
key with the most quota left: the last `RateLimit-Remaining` it saw in the current window, else
the limit minus its own count. Ties go to the key used least recently, so fresh keys alternate.

- **429:** the key is skipped until `Retry-After` (or `RateLimit-Reset`), and the other key is
  tried.
- **401:** the key is marked invalid and skipped until you replace it. A 403 means the library or
  plan denies access and leaves the key alone.
- A response reporting `RateLimit-Remaining: 0` marks the key exhausted until the reset.

## State

`${XDG_STATE_HOME:-~/.local/state}/docs-scout/usage.json` (mode 0600) stores, per key fingerprint
(`sha256(key)[:12]`, never the key or its label as the identity): limit, remaining, reset time,
local count, last use, and the exhausted and invalid flags. Because entries are keyed by
fingerprint, replacing a key in the config gives the new key a clean record. Removing the old one
leaves only an orphaned entry. Every per-window number is dropped once its reset time passes, so a
new month starts clean.

Parallel agents may run the script at the same time. Each run takes an `flock` on `usage.lock`
twice: once to choose a key and reserve one request, and once to merge the response headers. The
lock is never held during the HTTP request. Counts stay exact and one run cannot overwrite another's
flags. If the state directory cannot be written (a sandboxed harness, a read-only home), the script
warns and picks keys at random for that run.

`python3 scripts/c7search.py status` prints one line per key with its label, fingerprint, limit,
remaining, local count, reset time and flags. It never prints a key.

## Rotation

Replace the key in `config.toml` (keep the label if you like). The new fingerprint starts with a
clean record. To retry a key that was marked invalid by mistake, delete `usage.json`; it only holds
counters.
