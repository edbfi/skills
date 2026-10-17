"""Tests for scripts/c7search.py against a loopback fake of the Context7 search API.

Every test runs with temporary XDG directories and obviously fake keys, so nothing touches the
real config, state or cache, and nothing reaches context7.com.
"""
import contextlib
import email.utils
import http.server
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import ClassVar, cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/c7search.py'
spec = importlib.util.spec_from_file_location('c7search', SCRIPT)
assert spec is not None and spec.loader is not None
c7: ModuleType = importlib.util.module_from_spec(spec)
sys.modules['c7search'] = c7  # dataclasses look their module up while the class is created
spec.loader.exec_module(c7)
main = cast('Callable[[list[str]], int]', c7.main)
parse_reset = cast('Callable[[str | None, float], float]', c7.parse_reset)
next_month = cast('Callable[[float], float]', c7.next_month)
fingerprint = cast('Callable[[str], str]', c7.fingerprint)
iso = cast('Callable[[float], str]', c7.iso)

KEY_A = 'ctx7sk-test-0000-0000'
KEY_B = 'ctx7sk-test-1111-1111'
BODY = """Library: /vercel/next.js
### Caching
Source: https://nextjs.org/docs/app/getting-started/caching
Next.js caches fetch requests.
---
Library: /vercel/next.js
### Revalidating
Source: https://nextjs.org/docs/app/guides/revalidating
Use revalidateTag.
"""

Reply = tuple[int, dict[str, str], str]


class FakeAPI:
    """A ThreadingHTTPServer on 127.0.0.1 whose replies come from a per-test function."""

    def __init__(self, reply: Callable[[str, str], Reply]) -> None:
        self.requests: list[tuple[str, str]] = []  # (path, Authorization)
        api = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                auth = self.headers.get('Authorization') or ''
                api.requests.append((self.path, auth))
                status, headers, body = reply(self.path, auth)
                data = body.encode()
                self.send_response_only(status)  # send_response would also log every request
                for name, value in headers.items():
                    self.send_header(name, value)
                if 'Content-Length' not in headers:
                    self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                _ = self.wfile.write(data)

        self.server: http.server.ThreadingHTTPServer = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread: threading.Thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return f'http://127.0.0.1:{self.server.server_address[1]}/api/v3/search'

    def keys_used(self) -> list[str]:
        return [auth.removeprefix('Bearer ') for _, auth in self.requests]

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def ok(remaining: int, limit: int = 1000, reset: str = '') -> Reply:
    headers = {'Content-Type': 'text/plain', 'RateLimit-Limit': str(limit), 'RateLimit-Remaining': str(remaining)}
    if reset:
        headers['RateLimit-Reset'] = reset
    return 200, headers, BODY


def error(status: int, code: str, extra: dict[str, str] | None = None) -> Reply:
    return status, {'Content-Type': 'application/json', **(extra or {})}, json.dumps({'error': code, 'message': code})


class Base(unittest.TestCase):
    keys: ClassVar[list[tuple[str, str]]] = [('primary', KEY_A), ('secondary', KEY_B)]

    # Fixtures are built in __init__ rather than setUp: the repo types under Python 3.11, which
    # has no typing.override, and basedpyright recommended mode flags an unmarked setUp override.
    # unittest makes one instance per test method, so each test still gets fresh directories.
    # The environment is applied only around each CLI call (run_cli), never process-wide.
    def __init__(self, methodName: str = 'runTest') -> None:
        super().__init__(methodName)
        temp = tempfile.TemporaryDirectory(prefix='docs-scout-test-')
        self.addCleanup(temp.cleanup)
        self.tmp: Path = Path(temp.name)
        self.env: dict[str, str] = {
            'XDG_CONFIG_HOME': str(self.tmp / 'config'),
            'XDG_STATE_HOME': str(self.tmp / 'state'),
            'XDG_CACHE_HOME': str(self.tmp / 'cache'),
            'HOME': str(self.tmp / 'home'),
            'CONTEXT7_API_KEYS': '',
            'DOCS_SCOUT_API_BASE': 'http://127.0.0.1:9/api/v3/search',  # closed port until api() runs
        }
        self.write_config(self.keys)

    @property
    def config(self) -> Path:
        return self.tmp / 'config/docs-scout/config.toml'

    @property
    def state_file(self) -> Path:
        return self.tmp / 'state/docs-scout/usage.json'

    def write_config(self, keys: list[tuple[str, str]]) -> None:
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.parent.chmod(0o700)
        text = ''.join(f'[[keys]]\nlabel = "{label}"\nkey = "{key}"\n\n' for label, key in keys)
        _ = self.config.write_text(text)
        self.config.chmod(0o600)

    def api(self, reply: Callable[[str, str], Reply]) -> FakeAPI:
        fake = FakeAPI(reply)
        self.addCleanup(fake.close)
        self.env['DOCS_SCOUT_API_BASE'] = fake.base
        return fake

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.dict(os.environ, self.env), mock.patch.object(c7, 'RETRY_DELAY', 0),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            try:
                code = main(list(args))
            except SystemExit as exc:  # argparse rejects bad arguments by exiting
                code = exc.code if isinstance(exc.code, int) else 1
        return code, out.getvalue(), err.getvalue()

    def state(self) -> dict[str, dict[str, object]]:
        data = cast('dict[str, dict[str, dict[str, object]]]', json.loads(self.state_file.read_text()))
        return data['keys']


class Config(Base):
    def test_init_writes_private_template_once(self) -> None:
        self.config.unlink()
        self.config.parent.rmdir()
        code, out, _ = self.run_cli('init')
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), str(self.config))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.run_cli('init')[0], 73)
        code, _, err = self.run_cli('search', 'routing')
        self.assertEqual(code, 78)  # placeholders count as no key
        self.assertIn('no Context7 keys configured', err)

    def test_refuses_readable_config(self) -> None:
        self.config.chmod(0o644)
        code, _, err = self.run_cli('status')
        self.assertEqual(code, 78)
        self.assertIn('chmod 600', err)

    def test_refuses_symlinked_config(self) -> None:
        real = self.tmp / 'elsewhere.toml'
        _ = real.write_text(self.config.read_text())
        real.chmod(0o600)
        self.config.unlink()
        self.config.symlink_to(real)
        self.assertEqual(self.run_cli('status')[0], 78)

    def test_refuses_group_writable_dir(self) -> None:
        self.config.parent.chmod(0o770)
        code, _, err = self.run_cli('status')
        self.assertEqual(code, 78)
        self.assertIn('chmod 700', err)

    def test_env_keys_override_file(self) -> None:
        self.config.chmod(0o644)  # never read when the environment supplies keys
        fake = self.api(lambda _p, _a: ok(900))
        self.env['CONTEXT7_API_KEYS'] = f'{KEY_B}, <paste key>'
        code, _, err = self.run_cli('search', 'caching', '--no-cache')
        self.assertEqual(code, 0)
        self.assertEqual(fake.keys_used(), [KEY_B])
        self.assertIn('key=env1', err)

    def test_api_base_override_must_be_loopback(self) -> None:
        self.env['DOCS_SCOUT_API_BASE'] = 'https://example.com/api/v3/search'
        self.assertEqual(self.run_cli('search', 'caching')[0], 2)


class Requests(Base):
    def test_success_prints_body_and_sources(self) -> None:
        fake = self.api(lambda _p, _a: ok(900))
        code, out, err = self.run_cli('search', 'caching', '--library', 'next.js', '--version', '15')
        self.assertEqual(code, 0)
        self.assertEqual(out, BODY)
        self.assertIn('source: https://nextjs.org/docs/app/getting-started/caching', err)
        self.assertIn('cache=miss', err)
        path, auth = fake.requests[0]
        self.assertIn('query=caching', path)
        self.assertIn('library=next.js', path)
        self.assertIn('version=15', path)
        self.assertIn('type=txt', path)
        self.assertEqual(auth, f'Bearer {KEY_A}')

    def test_local_validation_sends_nothing(self) -> None:
        fake = self.api(lambda _p, _a: ok(900))
        libs = [arg for i in range(5) for arg in ('--library', f'lib{i}')]
        self.assertEqual(self.run_cli('search', 'q', *libs)[0], 2)
        self.assertEqual(self.run_cli('search', 'q', '--version', '15')[0], 2)
        self.assertEqual(self.run_cli('search', '  ')[0], 2)
        self.assertEqual(self.run_cli('search', 'q', '--type', 'xml')[0], 2)
        self.assertEqual(fake.requests, [])

    def test_not_found_is_exit_3(self) -> None:
        _ = self.api(lambda _p, _a: error(404, 'no_documentation_found'))
        code, out, err = self.run_cli('search', 'nothing', '--library', 'nope')
        self.assertEqual((code, out), (3, ''))
        self.assertIn('no documentation found', err)

    def test_bad_request_is_exit_2(self) -> None:
        _ = self.api(lambda _p, _a: error(400, 'validation_error'))
        self.assertEqual(self.run_cli('search', 'q')[0], 2)

    def test_server_error_retries_once(self) -> None:
        replies = [error(503, 'search_failed'), ok(900)]
        fake = self.api(lambda _p, _a: replies.pop(0))
        self.assertEqual(self.run_cli('search', 'q')[0], 0)
        self.assertEqual(len(fake.requests), 2)

    def test_persistent_server_error_is_exit_69(self) -> None:
        fake = self.api(lambda _p, _a: error(500, 'search_failed'))
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 69)
        self.assertIn('HTTP 500', err)
        self.assertEqual(len(fake.requests), 2)

    def test_network_error_is_exit_69(self) -> None:
        fake = self.api(lambda _p, _a: ok(900))
        fake.close()
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 69)
        self.assertIn('unreachable', err)

    def test_truncated_body_is_retried_then_exit_69(self) -> None:
        # Content-Length promises more than the body holds, so reading it raises IncompleteRead.
        fake = self.api(lambda _p, _a: (200, {'Content-Type': 'text/plain', 'Content-Length': '99999'}, BODY))
        code, out, err = self.run_cli('search', 'q')
        self.assertEqual((code, out), (69, ''))
        self.assertIn('unreachable', err)
        self.assertEqual(len(fake.requests), 2)

    def test_redirect_is_refused_and_key_not_forwarded(self) -> None:
        catcher = FakeAPI(lambda _p, _a: ok(900))
        self.addCleanup(catcher.close)
        fake = self.api(lambda _p, _a: (302, {'Location': catcher.base + '?query=x'}, ''))
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 69)
        self.assertIn('refusing redirect', err)
        self.assertEqual(catcher.requests, [])
        self.assertEqual(len(fake.requests), 1)

    def test_moved_library_names_the_new_id(self) -> None:
        body = json.dumps({'error': 'library_redirected', 'message': 'moved', 'redirectUrl': '/vercel/next.js'})
        catcher = FakeAPI(lambda _p, _a: ok(900))
        self.addCleanup(catcher.close)
        _ = self.api(lambda _p, _a: (301, {'Location': catcher.base, 'Content-Type': 'application/json'}, body))
        code, out, err = self.run_cli('search', 'q', '--library', 'zeit/next.js')
        self.assertEqual((code, out), (3, ''))
        self.assertIn('retry with --library /vercel/next.js', err)
        self.assertEqual(catcher.requests, [])

    def test_access_denied_is_exit_3_and_keeps_the_key(self) -> None:
        fake = self.api(lambda _p, _a: error(403, 'access_denied'))
        code, _, err = self.run_cli('search', 'q', '--library', '/acme/private')
        self.assertEqual(code, 3)
        self.assertIn('access denied', err)
        self.assertEqual(len(fake.requests), 1)
        self.assertNotIn('invalid', self.state()[fingerprint(KEY_A)])

    def test_truncates_to_max_chars(self) -> None:
        _ = self.api(lambda _p, _a: ok(900))
        code, out, err = self.run_cli('search', 'q', '--max-chars', '40')
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(BODY[:40]))
        self.assertIn('truncated, showing 40 of', out)
        self.assertIn('source: https://nextjs.org/docs/app/guides/revalidating', err)  # from the full body

    def test_json_sources(self) -> None:
        body = json.dumps({'codeSnippets': [{'codeId': 'https://a.example/x'}],
                           'infoSnippets': [{'pageId': 'https://b.example/y'}, {'pageId': 'not-a-url'}]})
        _ = self.api(lambda _p, _a: (200, {'Content-Type': 'application/json'}, body))
        code, out, err = self.run_cli('search', 'q', '--type', 'json')
        self.assertEqual((code, out), (0, body + '\n'))
        self.assertIn('source: https://a.example/x', err)
        self.assertIn('source: https://b.example/y', err)
        self.assertNotIn('not-a-url', err)


class Cache(Base):
    def test_hit_spends_no_request(self) -> None:
        fake = self.api(lambda _p, _a: ok(900))
        self.assertEqual(self.run_cli('search', 'q', '--library', 'b', '--library', 'a')[0], 0)
        code, out, err = self.run_cli('search', 'q', '--library', 'a', '--library', 'b')
        self.assertEqual((code, out), (0, BODY))
        self.assertIn('cache=hit', err)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(self.run_cli('search', 'q', '--library', 'a', '--library', 'b', '--no-cache')[0], 0)
        self.assertEqual(len(fake.requests), 2)

    def test_expired_entries_are_ignored_and_pruned(self) -> None:
        fake = self.api(lambda _p, _a: ok(900))
        self.assertEqual(self.run_cli('search', 'old')[0], 0)
        cache = self.tmp / 'cache/docs-scout'
        stale = time.time() - 2 * 86400
        for path in cache.iterdir():
            os.utime(path, (stale, stale))
        self.assertEqual(self.run_cli('search', 'old')[0], 0)
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual(len(list(cache.iterdir())), 1)


class Balancing(Base):
    def test_prefers_key_with_more_quota(self) -> None:
        remaining = {KEY_A: 10, KEY_B: 500}
        fake = self.api(lambda _p, auth: ok(remaining[auth.removeprefix('Bearer ')]))
        for _ in range(3):
            self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A, KEY_B, KEY_B])
        state = self.state()
        self.assertEqual(state[fingerprint(KEY_A)]['remaining'], 10)
        self.assertEqual(state[fingerprint(KEY_B)]['count'], 2)

    def test_ties_go_to_least_recently_used(self) -> None:
        fake = self.api(lambda _p, _a: (200, {'Content-Type': 'text/plain'}, BODY))  # no quota headers
        for _ in range(4):
            self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A, KEY_B, KEY_A, KEY_B])

    def test_rate_limit_fails_over_and_sticks(self) -> None:
        def reply(_p: str, auth: str) -> Reply:
            if auth.endswith(KEY_A):
                return error(429, 'rate_limited', {'Retry-After': '3600'})
            return ok(800)
        fake = self.api(reply)
        before = time.time()
        code, _, err = self.run_cli('search', 'q', '--no-cache')
        self.assertEqual(code, 0)
        self.assertIn('key primary got HTTP 429', err)
        until = cast('float', self.state()[fingerprint(KEY_A)]['exhausted_until'])
        self.assertAlmostEqual(until, before + 3600, delta=30)
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A, KEY_B, KEY_B])

    def test_all_exhausted_is_exit_75_with_reset(self) -> None:
        reset = next_month(time.time())
        fake = self.api(lambda _p, _a: error(429, 'rate_limited', {'RateLimit-Reset': str(int(reset))}))
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 75)
        self.assertIn(f'until {iso(reset)}', err)
        self.assertEqual(sorted(fake.keys_used()), sorted([KEY_A, KEY_B]))

    def test_exhausted_keys_send_nothing_until_reset(self) -> None:
        fake = self.api(lambda _p, _a: error(429, 'rate_limited', {'Retry-After': '600'}))
        self.assertEqual(self.run_cli('search', 'q')[0], 75)
        self.assertEqual(self.run_cli('search', 'q2')[0], 75)
        self.assertEqual(len(fake.requests), 2)  # the second search never reached the server

    def test_zero_remaining_marks_key_exhausted(self) -> None:
        reset = str(int(next_month(time.time())))
        fake = self.api(lambda _p, auth: ok(0 if auth.endswith(KEY_A) else 700, reset=reset))
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        for _ in range(2):
            self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A, KEY_B, KEY_B])

    def test_invalid_key_is_skipped_until_replaced(self) -> None:
        good = {KEY_B, 'ctx7sk-test-2222-2222'}
        fake = self.api(lambda _p, auth: ok(900) if auth.removeprefix('Bearer ') in good
                        else error(401, 'invalid_api_key'))
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertTrue(self.state()[fingerprint(KEY_A)]['invalid'])
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A, KEY_B, KEY_B])
        self.write_config([('primary', 'ctx7sk-test-2222-2222'), ('secondary', KEY_B)])
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used()[-1], 'ctx7sk-test-2222-2222')

    def test_all_invalid_is_exit_78(self) -> None:
        _ = self.api(lambda _p, _a: error(401, 'invalid_api_key'))
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 78)
        self.assertIn('rejected', err)

    def test_month_rollover_drops_stale_quota(self) -> None:
        past = time.time() - 60
        stale = {'reset': past, 'remaining': 0, 'exhausted_until': past - 1, 'count': 999, 'limit': 1000}
        self.state_file.parent.mkdir(parents=True)
        _ = self.state_file.write_text(json.dumps({'version': 1, 'keys': {
            fingerprint(KEY_A): stale, fingerprint(KEY_B): dict(stale, remaining=5)}}))
        fake = self.api(lambda _p, _a: ok(999))
        self.assertEqual(self.run_cli('search', 'q', '--no-cache')[0], 0)
        self.assertEqual(fake.keys_used(), [KEY_A])
        entry = self.state()[fingerprint(KEY_A)]
        self.assertEqual(entry['count'], 1)
        self.assertGreater(cast('float', entry['reset']), time.time())
        self.assertEqual(self.state()[fingerprint(KEY_B)].get('remaining'), None)

    def test_unwritable_state_still_searches(self) -> None:
        blocker = self.tmp / 'state-file'
        _ = blocker.write_text('')
        self.env['XDG_STATE_HOME'] = str(blocker)  # mkdir under a regular file fails
        _ = self.api(lambda _p, _a: ok(900))
        code, _, err = self.run_cli('search', 'q')
        self.assertEqual(code, 0)
        self.assertIn('state not writable', err)


class Secrets(Base):
    def test_key_never_printed_or_stored(self) -> None:
        def reply(_p: str, auth: str) -> Reply:
            if auth.endswith(KEY_A):  # a hostile or buggy server echoing the key back
                return 401, {'Content-Type': 'application/json'}, json.dumps({'error': 'bad', 'message': auth})
            return ok(900)
        _ = self.api(reply)
        outputs = [self.run_cli('search', 'q'), self.run_cli('status'), self.run_cli('search', 'q')]
        written = [p.read_bytes() for p in self.tmp.rglob('*') if p.is_file() and p != self.config]
        for secret in (KEY_A, KEY_B):
            for code, out, err in outputs:
                self.assertNotIn(secret, out + err, code)
            for data in written:
                self.assertNotIn(secret.encode(), data)
        self.assertIn('[redacted]', outputs[0][2])


class ResetParsing(unittest.TestCase):
    now: float = 1792000000.0  # 2026-10-15

    def test_epoch(self) -> None:
        self.assertEqual(parse_reset('1793491200', self.now), 1793491200)

    def test_delta_seconds(self) -> None:
        self.assertEqual(parse_reset('3600', self.now), self.now + 3600)

    def test_http_date(self) -> None:
        when = self.now + 7200
        self.assertEqual(parse_reset(email.utils.formatdate(when, usegmt=True), self.now), int(when))

    def test_missing_means_next_month(self) -> None:
        self.assertEqual(parse_reset(None, self.now), 1793491200)
        self.assertEqual(parse_reset('soon', self.now), 1793491200)

    def test_clamped(self) -> None:
        self.assertEqual(parse_reset('0', self.now), self.now + 60)
        self.assertEqual(parse_reset('9999999999', self.now), 1793491200 + 86400)

    def test_december_rolls_the_year(self) -> None:
        self.assertEqual(next_month(1796083200), 1798761600)  # 2026-12-01 -> 2027-01-01


class Concurrency(Base):
    def test_parallel_searches_count_exactly(self) -> None:
        lock = threading.Lock()
        remaining = {KEY_A: 600, KEY_B: 600}

        def reply(_p: str, auth: str) -> Reply:
            time.sleep(0.05)
            with lock:
                key = auth.removeprefix('Bearer ')
                remaining[key] -= 1
                return ok(remaining[key])
        fake = self.api(reply)
        env = {**os.environ, **self.env}
        procs = [subprocess.Popen([sys.executable, '-I', '-B', str(SCRIPT), 'search', f'q{i}'], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                 for i in range(8)]
        codes = [p.wait(timeout=60) for p in procs]
        for p in procs:
            if p.stderr:
                p.stderr.close()
        self.assertEqual(codes, [0] * 8)
        self.assertEqual(len(fake.requests), 8)
        state = self.state()
        self.assertEqual(sum(cast('int', e['count']) for e in state.values()), 8)
        self.assertEqual(sum(600 - cast('int', e['remaining']) for e in state.values()), 8)


if __name__ == '__main__':
    _ = unittest.main()
