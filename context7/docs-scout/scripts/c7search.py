#!/usr/bin/env python3
"""Search Context7 (GET /api/v3/search) with up to two API keys balanced across their quotas.

Usage:
  c7search.py init                          write a template config.toml (0600) to paste keys into
  c7search.py search QUERY [--library L]... [--language X] [--version V]
                     [--type txt|json] [--max-chars N] [--no-cache]
  c7search.py status                        quota and health per key (label + fingerprint only)

Keys come from ${XDG_CONFIG_HOME:-~/.config}/docs-scout/config.toml, or from CONTEXT7_API_KEYS
(comma-separated, for CI). Keys are never read from argv or stdin and never printed.
State lives in ${XDG_STATE_HOME:-~/.local/state}/docs-scout/usage.json, the response cache in
${XDG_CACHE_HOME:-~/.cache}/docs-scout/. See references/context7-api.md and references/config.md.

Exit status: 0 results, 2 usage or 400, 3 nothing usable for this request (404 no documentation,
403 access denied for the library, or 301 library moved: stderr names the new ID), 69 Context7
unreachable or failing (5xx, network, unexpected redirect), 73 init found an existing config,
75 every key is rate-limited (stderr names the time it resets), 78 no usable key (missing,
placeholder, rejected with 401, or a config file with unsafe permissions).
"""
from __future__ import annotations

import argparse
import calendar
import contextlib
import email.utils
import fcntl
import hashlib
import http.client
import ipaddress
import json
import os
import random
import stat
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Generator
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import IO, cast, final

VERSION = '1.0.0'
API_BASE = 'https://context7.com/api/v3/search'
USER_AGENT = f'docs-scout/{VERSION}'
TIMEOUT = 30
RETRY_DELAY = 2.0
CACHE_TTL = 24 * 3600
DEFAULT_LIMIT = 1000
MAX_LIBRARIES = 4
MIN_HOLD = 60

EX_OK, EX_USAGE, EX_EMPTY = 0, 2, 3
EX_UNAVAILABLE, EX_CANTCREAT, EX_TEMPFAIL, EX_CONFIG = 69, 73, 75, 78

TEMPLATE = """\
# docs-scout: Context7 API keys (https://context7.com/dashboard). Keep this file chmod 600.
# Paste each key between the quotes. Entries whose key is empty or starts with "<" are ignored.
[[keys]]
label = "primary"
key = "<paste key>"

[[keys]]
label = "secondary"
key = "<paste key>"
"""


@final
class Fail(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code: int = code


@dataclass(frozen=True)
class Key:
    label: str
    secret: str

    @property
    def fp(self) -> str:
        return fingerprint(self.secret)


@dataclass
class Response:
    status: int
    headers: Message
    body: str


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


def xdg(var: str, default: str) -> Path:
    value = os.environ.get(var, '')
    base = Path(value) if value and os.path.isabs(value) else Path.home() / default
    return base / 'docs-scout'


def config_path() -> Path:
    return xdg('XDG_CONFIG_HOME', '.config') / 'config.toml'


def state_dir() -> Path:
    return xdg('XDG_STATE_HOME', '.local/state')


def cache_dir() -> Path:
    return xdg('XDG_CACHE_HOME', '.cache')


def warn(message: str) -> None:
    print(f'docs-scout: {message}', file=sys.stderr)


# ---------------------------------------------------------------- time


def next_month(now: float) -> float:
    t = time.gmtime(now)
    year, month = (t.tm_year + 1, 1) if t.tm_mon == 12 else (t.tm_year, t.tm_mon + 1)
    return float(calendar.timegm((year, month, 1, 0, 0, 0)))


def parse_reset(value: str | None, now: float) -> float:
    """An absolute reset time from RateLimit-Reset or Retry-After, clamped to a sane window.

    Context7 sends an epoch (1793491200 = 2026-11-01T00:00Z); RFC-style values are delta seconds,
    and Retry-After may also be an HTTP-date. Missing or unparsable means the next calendar month.
    """
    ceiling = next_month(now) + 86400
    at: float | None = None
    text = (value or '').strip()
    if text:
        try:
            number = float(text)
        except ValueError:
            with contextlib.suppress(TypeError, ValueError, IndexError):
                at = email.utils.parsedate_to_datetime(text).timestamp()
        else:
            at = number if number > 1e9 else now + number
    if at is None:
        at = next_month(now)
    return min(max(at, now + MIN_HOLD), ceiling)


def iso(ts: float) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))


# ---------------------------------------------------------------- config


def check_private(path: Path, want_dir: bool) -> None:
    try:
        st = path.lstat()
    except FileNotFoundError:
        fix = f'python3 {Path(__file__).resolve()} init'
        raise Fail(EX_CONFIG, f'{path} does not exist; the user can create it with: {fix}') from None
    kind_ok = stat.S_ISDIR(st.st_mode) if want_dir else stat.S_ISREG(st.st_mode)
    if stat.S_ISLNK(st.st_mode) or not kind_ok:
        raise Fail(EX_CONFIG, f'{path} must be a real {"directory" if want_dir else "file"}, not a symlink')
    if st.st_uid != os.getuid():
        raise Fail(EX_CONFIG, f'{path} is not owned by you')
    if want_dir and st.st_mode & 0o022:
        raise Fail(EX_CONFIG, f'{path} is group/other-writable; fix with: chmod 700 {path}')
    if not want_dir and st.st_mode & 0o077:
        raise Fail(EX_CONFIG, f'{path} is readable by others; fix with: chmod 600 {path}')


def key_source() -> str:
    return 'CONTEXT7_API_KEYS' if os.environ.get('CONTEXT7_API_KEYS', '').strip() else str(config_path())


def usable(secret: str) -> bool:
    return bool(secret) and not secret.startswith('<')


def load_keys() -> list[Key]:
    env = os.environ.get('CONTEXT7_API_KEYS', '')
    if env.strip():
        secrets = [s.strip() for s in env.split(',') if usable(s.strip())]
        return [Key(f'env{i}', s) for i, s in enumerate(secrets, 1)]
    path = config_path()
    check_private(path.parent, want_dir=True)
    check_private(path, want_dir=False)
    try:
        data: dict[str, object] = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise Fail(EX_CONFIG, f'cannot parse {path}: {type(exc).__name__}') from None
    entries = data.get('keys', [])
    keys: list[Key] = []
    if isinstance(entries, list):
        for i, entry in enumerate(cast('list[object]', entries), 1):
            if not isinstance(entry, dict):
                continue
            item = cast('dict[str, object]', entry)
            secret, label = item.get('key'), item.get('label')
            if isinstance(secret, str) and usable(secret.strip()):
                keys.append(Key(label if isinstance(label, str) and label else f'key{i}', secret.strip()))
    return keys


def cmd_init() -> int:
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f'docs-scout: {path} already exists; edit it instead', file=sys.stderr)
        return EX_CANTCREAT
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        _ = fh.write(TEMPLATE)
    path.chmod(0o600)
    print(path)
    print('Open the file in an editor and paste your Context7 keys; never paste them into a chat.', file=sys.stderr)
    return EX_OK


# ---------------------------------------------------------------- state

Entry = dict[str, object]


def num(entry: Entry, name: str) -> float | None:
    value = entry.get(name)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


@final
class State:
    """usage.json keyed by key fingerprint, guarded by an flock on usage.lock.

    Persistence is best-effort: if the state directory is unusable (a sandboxed harness, a
    read-only home), the run warns once and balances randomly in memory instead.
    """

    def __init__(self) -> None:
        self.dir = state_dir()
        self.path = self.dir / 'usage.json'
        self.memory: dict[str, Entry] = {}
        self.persistent = True
        try:
            self.dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            with self.locked():
                pass
        except OSError as exc:
            warn(f'state not writable ({type(exc).__name__}); balancing keys randomly this run')
            self.persistent = False

    @contextlib.contextmanager
    def locked(self) -> Generator[None]:
        if not self.persistent:
            yield
            return
        fd = os.open(self.dir / 'usage.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def load(self, now: float) -> dict[str, Entry]:
        raw: object = {}
        if self.persistent:
            try:
                raw = cast('object', json.loads(self.path.read_text(encoding='utf-8')))
            except FileNotFoundError:
                raw = {}
            except (OSError, ValueError):
                warn(f'{self.path} unreadable; starting fresh')
                raw = {}
        else:
            raw = {'keys': self.memory}
        keys_obj = cast('dict[str, object]', raw).get('keys') if isinstance(raw, dict) else None
        entries: dict[str, Entry] = {}
        if isinstance(keys_obj, dict):
            for fp, entry in cast('dict[str, object]', keys_obj).items():
                if isinstance(entry, dict):
                    entries[fp] = rollover(cast('Entry', entry), now)
        return entries

    def save(self, entries: dict[str, Entry]) -> None:
        if not self.persistent:
            self.memory = entries
            return
        tmp = self.path.with_suffix(f'.{os.getpid()}.tmp')
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump({'version': 1, 'keys': entries}, fh, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except OSError as exc:
            warn(f'could not save state ({type(exc).__name__})')
            with contextlib.suppress(OSError):
                tmp.unlink()


def rollover(entry: Entry, now: float) -> Entry:
    """Drop every per-window number once its reset time has passed; keep limit and invalid."""
    reset = num(entry, 'reset')
    if reset is not None and now < reset:
        return entry
    fresh: Entry = {'reset': next_month(now), 'count': 0}
    for name in ('limit', 'invalid', 'last_used', 'label'):
        if name in entry:
            fresh[name] = entry[name]
    return fresh


def effective_remaining(entry: Entry) -> float:
    remaining = num(entry, 'remaining')
    if remaining is not None:
        return remaining
    return (num(entry, 'limit') or DEFAULT_LIMIT) - (num(entry, 'count') or 0)


def eligible(entry: Entry, now: float) -> bool:
    if entry.get('invalid') is True:
        return False
    until = num(entry, 'exhausted_until')
    return until is None or now >= until


def pick(keys: list[Key], entries: dict[str, Entry], now: float, tried: set[str], persistent: bool) -> Key | None:
    candidates = [k for k in keys if k.fp not in tried and eligible(entries.get(k.fp, {}), now)]
    if not candidates:
        return None
    if not persistent:
        return random.choice(candidates)
    return max(candidates, key=lambda k: (effective_remaining(entries.get(k.fp, {})),
                                          -(num(entries.get(k.fp, {}), 'last_used') or 0.0)))


def reserve(entries: dict[str, Entry], key: Key, now: float) -> None:
    entry = entries.setdefault(key.fp, {'reset': next_month(now), 'count': 0})
    entry['label'] = key.label
    entry['count'] = int(num(entry, 'count') or 0) + 1
    entry['last_used'] = now
    remaining = num(entry, 'remaining')
    if remaining is not None:
        entry['remaining'] = max(int(remaining) - 1, 0)


def header_int(headers: Message, name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(float(value.strip()))
    except ValueError:
        return None


def merge(entries: dict[str, Entry], key: Key, resp: Response, now: float) -> Entry:
    entry = entries.setdefault(key.fp, {'reset': next_month(now), 'count': 1})
    entry['label'] = key.label
    remaining = header_int(resp.headers, 'RateLimit-Remaining')
    limit = header_int(resp.headers, 'RateLimit-Limit')
    reset_header = resp.headers.get('RateLimit-Reset')
    if reset_header is not None:
        reset = parse_reset(reset_header, now)
        old_reset = num(entry, 'reset')
        if old_reset is not None and reset > old_reset + MIN_HOLD:
            _ = entry.pop('remaining', None)  # the server already moved to a new window
            _ = entry.pop('exhausted_until', None)
        entry['reset'] = reset
    if limit is not None and limit > 0:
        entry['limit'] = limit
    if remaining is not None:
        current = num(entry, 'remaining')
        # Responses can arrive out of order; within one window the quota only goes down.
        entry['remaining'] = remaining if current is None else min(int(current), remaining)
    if resp.status == 429:
        retry_after = resp.headers.get('Retry-After') or reset_header
        entry['exhausted_until'] = parse_reset(retry_after, now)
        entry['remaining'] = 0
    elif resp.status == 401:
        entry['invalid'] = True
    elif resp.status == 200:
        _ = entry.pop('invalid', None)
        if num(entry, 'remaining') == 0:
            entry['exhausted_until'] = num(entry, 'reset') or next_month(now)
    return entry


# ---------------------------------------------------------------- transport


@final
class NoRedirect(urllib.request.BaseHandler):
    """Hand every 30x back as an error before the stock redirect handler (order 500) follows it.

    The key must never travel to another URL, and Context7's own 301 ("library redirected")
    carries the new library ID in its JSON body rather than asking to be followed.
    """

    handler_order = 400

    def refuse(self, req: urllib.request.Request, fp: IO[bytes], code: int, msg: str, headers: Message) -> None:
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

    http_error_301 = http_error_302 = http_error_303 = http_error_307 = http_error_308 = refuse


def api_base() -> str:
    override = os.environ.get('DOCS_SCOUT_API_BASE', '')
    if not override:
        return API_BASE
    parts = urllib.parse.urlsplit(override)
    try:
        loopback = parts.hostname is not None and ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        loopback = False
    if parts.scheme not in ('http', 'https') or not loopback:
        raise Fail(EX_USAGE, 'DOCS_SCOUT_API_BASE must point at 127.0.0.1 or ::1 (tests only)')
    return override


def request(url: str, key: Key) -> Response:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                               'Accept': 'application/json, text/plain'})
    req.add_unredirected_header('Authorization', f'Bearer {key.secret}')
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with cast('http.client.HTTPResponse', opener.open(req, timeout=TIMEOUT)) as resp:
            return Response(resp.status, resp.headers, resp.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.headers, exc.read().decode('utf-8', 'replace'))


def json_field(body: str, name: str) -> str | None:
    try:
        data = cast('object', json.loads(body))
    except ValueError:
        return None
    value = cast('dict[str, object]', data).get(name) if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def api_message(body: str) -> str:
    try:
        data = cast('object', json.loads(body))
    except ValueError:
        return body.strip()[:300]
    if isinstance(data, dict):
        obj = cast('dict[str, object]', data)
        parts = [str(obj[k]) for k in ('error', 'message') if obj.get(k)]
        return ': '.join(parts)[:300]
    return body.strip()[:300]


# ---------------------------------------------------------------- output


def sources(body: str, kind: str) -> list[str]:
    found: list[str] = []
    if kind == 'json':
        with contextlib.suppress(ValueError):
            data = cast('object', json.loads(body))
            if isinstance(data, dict):
                obj = cast('dict[str, object]', data)
                for group, field in (('codeSnippets', 'codeId'), ('infoSnippets', 'pageId')):
                    items = obj.get(group)
                    if isinstance(items, list):
                        for item in cast('list[object]', items):
                            if isinstance(item, dict):
                                value = cast('dict[str, object]', item).get(field)
                                if isinstance(value, str):
                                    found.append(value)
    else:
        found = [line[len('Source:'):].strip() for line in body.splitlines() if line.startswith('Source:')]
    unique: list[str] = []
    for url in found:
        if url.startswith(('http://', 'https://')) and url not in unique:
            unique.append(url)
    return unique


def redact(text: str, keys: list[Key]) -> str:
    for key in keys:
        text = text.replace(key.secret, '[redacted]')
    return text


def emit(body: str, kind: str, max_chars: int, cached: Path | None, trailer: str) -> None:
    urls = sources(body, kind)
    if len(body) > max_chars:
        where = f'full body: {cached}' if cached else 'rerun with a larger --max-chars'
        body = body[:max_chars] + f'\n[docs-scout: truncated, showing {max_chars} of {len(body)} chars; {where}]\n'
    print(body, end='' if body.endswith('\n') else '\n', flush=True)
    print(f'docs-scout: {trailer}', file=sys.stderr)
    for url in urls:
        print(f'source: {url}', file=sys.stderr)


# ---------------------------------------------------------------- cache


def cache_key(params: list[tuple[str, str]]) -> str:
    return hashlib.sha256(json.dumps(sorted(params)).encode()).hexdigest()


def cache_get(name: str, now: float) -> tuple[str, Path] | None:
    path = cache_dir() / name
    try:
        if now - path.stat().st_mtime > CACHE_TTL:
            return None
        return path.read_text(encoding='utf-8'), path
    except (OSError, UnicodeDecodeError):
        return None


def cache_put(name: str, body: str, now: float) -> Path | None:
    directory = cache_dir()
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        for old in directory.iterdir():
            with contextlib.suppress(OSError):
                if old.is_file() and now - old.stat().st_mtime > CACHE_TTL:
                    old.unlink()
        path = directory / name
        tmp = path.with_suffix(f'.{os.getpid()}.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            _ = fh.write(body)
        os.replace(tmp, path)
        return path
    except OSError:
        return None


# ---------------------------------------------------------------- commands


def validate(args: Args) -> list[tuple[str, str]]:
    query = args.query.strip()
    libraries = [lib.strip() for lib in args.library or [] if lib.strip()]
    if not query:
        raise Fail(EX_USAGE, 'QUERY must not be empty')
    if len(libraries) > MAX_LIBRARIES:
        raise Fail(EX_USAGE, f'at most {MAX_LIBRARIES} --library values are allowed')
    if args.version and not libraries:
        raise Fail(EX_USAGE, '--version needs at least one --library')
    if args.max_chars < 1:
        raise Fail(EX_USAGE, '--max-chars must be positive')
    params = [('query', query)] + [('library', lib) for lib in libraries]
    if args.language:
        params.append(('language', args.language))
    if args.version:
        params.append(('version', args.version))
    params.append(('type', args.type))
    return params


def cmd_search(args: Args) -> int:
    params = validate(args)
    kind = args.type
    max_chars = args.max_chars
    base = api_base()
    name = f'{cache_key(params)}.{kind}'
    now = time.time()
    if not args.no_cache and (hit := cache_get(name, now)):
        emit(hit[0], kind, max_chars, hit[1], 'key=- cache=hit')
        return EX_OK

    keys = load_keys()
    if not keys:
        raise Fail(EX_CONFIG, f'no Context7 keys configured; paste them into {key_source()} (run init first)')
    url = f'{base}?{urllib.parse.urlencode(params)}'
    state = State()
    tried: set[str] = set()
    retried = False  # one retry per search, on the same key, for 5xx and network errors
    while True:
        now = time.time()
        with state.locked():
            entries = state.load(now)
            key = pick(keys, entries, now, tried, state.persistent)
            if key is None:
                break
            reserve(entries, key, now)
            state.save(entries)
        while True:
            try:
                resp: Response | str = request(url, key)
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                # HTTPException covers a truncated or malformed response (IncompleteRead, BadStatusLine)
                resp = str(exc.reason if isinstance(exc, urllib.error.URLError) else exc) or type(exc).__name__
            if isinstance(resp, Response) and resp.status < 500:
                break
            if retried:
                if isinstance(resp, str):
                    raise Fail(EX_UNAVAILABLE, f'Context7 unreachable: {redact(resp, keys)}')
                detail = redact(api_message(resp.body), keys)
                raise Fail(EX_UNAVAILABLE, f'Context7 failing: HTTP {resp.status} {detail}')
            retried = True
            time.sleep(RETRY_DELAY)
            with state.locked():
                entries = state.load(time.time())
                reserve(entries, key, time.time())
                state.save(entries)
        now = time.time()
        with state.locked():
            entries = state.load(now)
            entry = merge(entries, key, resp, now)
            state.save(entries)
        reset = iso(num(entry, 'reset') or next_month(now))
        info = f'key={key.label} remaining={int(effective_remaining(entry))} reset={reset}'
        if resp.status == 200:
            cached = cache_put(name, resp.body, now)
            emit(resp.body, kind, max_chars, cached, f'{info} cache=miss')
            return EX_OK
        message = redact(api_message(resp.body), keys)
        if resp.status == 404:
            print(f'docs-scout: no documentation found ({message}); {info}', file=sys.stderr)
            return EX_EMPTY
        if resp.status == 403:  # library permissions or plan, not the key (bad keys get 401)
            print(f'docs-scout: access denied for this request ({message}); {info}', file=sys.stderr)
            return EX_EMPTY
        if 300 <= resp.status < 400:
            moved = json_field(resp.body, 'redirectUrl')
            if moved and moved.isprintable() and len(moved) <= 200:
                print(f'docs-scout: library moved; retry with --library {moved}', file=sys.stderr)
                return EX_EMPTY
            raise Fail(EX_UNAVAILABLE, f'refusing redirect (HTTP {resp.status}); the key is never sent elsewhere')
        if resp.status in (401, 429):
            warn(f'key {key.label} got HTTP {resp.status} ({message}); trying the next key')
            tried.add(key.fp)
            continue
        raise Fail(EX_USAGE, f'Context7 rejected the request: HTTP {resp.status} {message}')

    now = time.time()
    with state.locked():
        entries = state.load(now)
    waits = [num(entries.get(k.fp, {}), 'exhausted_until') for k in keys
             if entries.get(k.fp, {}).get('invalid') is not True]
    waits = [w for w in waits if w is not None and w > now]
    if waits:
        raise Fail(EX_TEMPFAIL, f'Context7 quota exhausted on every key until {iso(min(waits))}')
    raise Fail(EX_CONFIG, f'every Context7 key was rejected (401 invalid_api_key); replace them in {key_source()}')


def cmd_status() -> int:
    keys = load_keys()
    if not keys:
        raise Fail(EX_CONFIG, f'no Context7 keys configured in {key_source()}')
    state = State()
    now = time.time()
    with state.locked():
        entries = state.load(now)
    for key in keys:
        entry = entries.get(key.fp, {})
        flags: list[str] = []
        if entry.get('invalid') is True:
            flags.append('invalid')
        until = num(entry, 'exhausted_until')
        if until is not None and now < until:
            flags.append(f'exhausted-until={iso(until)}')
        remaining = num(entry, 'remaining')
        fields = [key.label, f'fp={key.fp}', f'limit={int(num(entry, "limit") or DEFAULT_LIMIT)}',
                  f'remaining={"?" if remaining is None else int(remaining)}',
                  f'local-count={int(num(entry, "count") or 0)}',
                  f'reset={iso(num(entry, "reset") or next_month(now))}', ','.join(flags) or 'ok']
        print(' '.join(fields))
    return EX_OK


class Args(argparse.Namespace):
    command: str = ''
    query: str = ''
    library: list[str] | None = None
    language: str | None = None
    version: str | None = None
    type: str = 'txt'
    max_chars: int = 12000
    no_cache: bool = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='c7search.py', description='Context7 search with balanced API keys.')
    sub = parser.add_subparsers(dest='command', required=True)
    _ = sub.add_parser('init', help='write a template config.toml (0600)')
    _ = sub.add_parser('status', help='quota and health per key')
    search = sub.add_parser('search', help='search Context7')
    _ = search.add_argument('query')
    _ = search.add_argument('--library', action='append', help='library hint (name or /owner/repo), up to 4')
    _ = search.add_argument('--language')
    _ = search.add_argument('--version', help='library version; needs --library')
    _ = search.add_argument('--type', choices=('txt', 'json'), default='txt')
    _ = search.add_argument('--max-chars', type=int, default=12000)
    _ = search.add_argument('--no-cache', action='store_true')
    args = parser.parse_args(argv, namespace=Args())
    try:
        if args.command == 'init':
            return cmd_init()
        if args.command == 'status':
            return cmd_status()
        return cmd_search(args)
    except Fail as exc:
        print(f'docs-scout: {exc}', file=sys.stderr)
        return exc.code


if __name__ == '__main__':
    sys.exit(main())
