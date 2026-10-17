"""Offline tests for registry_versions.py: version ordering, constraints, feeds and the CLI."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_registry() -> ModuleType:
    spec = importlib.util.spec_from_file_location("registry_versions", SCRIPTS / "registry_versions.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["registry_versions"] = module  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(module)
    return module


class VersionLike(Protocol):
    pre: tuple[str, ...] | None
    suffixed: bool

    def key(self) -> tuple[tuple[int, ...], int, tuple[tuple[int, int, str], ...]]: ...


REGISTRY = load_registry()
# These signatures are defined by the local module loaded from the path above.
main = cast("Callable[[list[str]], int]", REGISTRY.main)
is_stable = cast("Callable[[str], bool]", REGISTRY.is_stable)
parse_version = cast("Callable[[str], VersionLike | None]", REGISTRY.parse_version)
parse_constraint = cast("Callable[[str], object]", REGISTRY.parse_constraint)
select = cast("Callable[[object, object | None], str | None]", REGISTRY.select)
listing_type = cast("Callable[..., object]", REGISTRY.Listing)

NPM_DOC = {
    "dist-tags": {"latest": "7.0.2", "rc": "1.0.0-rc.4", "next": "7.1.0-dev.20261001"},
    "versions": {v: {"engines": {"node": ">=18"}, "peerDependencies": {"svelte": "^5"}} for v in
                 ("6.0.1", "6.0.3", "6.1.0", "7.0.2", "7.1.0-dev.20261001", "1.0.0-rc.3", "1.0.0-rc.4",
                  "1.0.0-rc.5-5935859")},
}


def fake_fetch(responses: dict[str, object]) -> Callable[[str], str]:
    def fetch(url: str) -> str:
        for prefix, body in responses.items():
            if url.startswith(prefix):
                return body if isinstance(body, str) else json.dumps(body)
        raise OSError(f"unexpected URL {url}")
    return fetch


def run_main(components: list[dict[str, object]], responses: dict[str, object], *extra: str) -> tuple[int, dict[str, object], str]:
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "components.json"
        _ = source.write_text(json.dumps(components))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(REGISTRY, "fetch_text", side_effect=fake_fetch(responses)):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["registry_versions.py", str(source), *extra])
    snapshot = cast("dict[str, object]", json.loads(stdout.getvalue())) if stdout.getvalue() else {}
    return code, snapshot, stderr.getvalue()


def entries(snapshot: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", snapshot["components"])


class VersionModel(unittest.TestCase):
    def test_stability_and_suffixes(self) -> None:
        for raw in ("1.2.3", "v1.2.3", "1.2.3+build.4", "1.2.post1", "1.0.0.Final", "5.3.0-RELEASE"):
            self.assertTrue(is_stable(raw), raw)
        for raw in ("2.0.0-beta.1", "1.0rc1", "3.14.0rc3", "1.0.0-rc.5-5935859", "0.0.0-canary-20240101"):
            self.assertFalse(is_stable(raw), raw)
        suffixed = {raw: (parse_version(raw) or self.fail(raw)).suffixed
                    for raw in ("1.0.0-rc.4", "1.0.0-rc.5-5935859", "1.0.0-rc.5-ab785fc", "7.1.0-dev.20261001")}
        self.assertEqual({"1.0.0-rc.4": False, "1.0.0-rc.5-5935859": True, "1.0.0-rc.5-ab785fc": True,
                          "7.1.0-dev.20261001": True}, suffixed)
        self.assertIsNone(parse_version("latest"))

    def test_semver_prerelease_ordering(self) -> None:
        ordered = sorted(["1.0.0", "1.0.0-rc.10", "1.0.0-beta.2", "1.0.0-rc.9", "0.9.9"],
                         key=lambda raw: (parse_version(raw) or self.fail(raw)).key())
        self.assertEqual(["0.9.9", "1.0.0-beta.2", "1.0.0-rc.9", "1.0.0-rc.10", "1.0.0"], ordered)

    def test_constraints_select_lines(self) -> None:
        found = listing_type(["6.0.1", "6.0.3", "6.1.0", "7.0.2", "7.1.0-beta.1"])
        cases: dict[str | None, str | None] = {None: "7.0.2", "6": "6.1.0", "6.0": "6.0.3", "6.0.1": "6.0.1",
                                               "7": "7.0.2", "8": None, "6.0.2": None}
        for constraint, expected in cases.items():
            with self.subTest(constraint=constraint):
                self.assertEqual(expected, select(found, parse_constraint(constraint) if constraint else None))

    def test_prerelease_lines_prefer_dist_tag_and_skip_suffixed_builds(self) -> None:
        versions = ["0.45.4", "1.0.0-rc.3", "1.0.0-rc.4", "1.0.0-rc.5-5935859"]
        self.assertEqual("1.0.0-rc.4", select(listing_type(versions, dist_tags={"rc": "1.0.0-rc.4"}), parse_constraint("1.0-rc")))
        self.assertEqual("1.0.0-rc.4", select(listing_type(versions), parse_constraint("1.0-rc")))
        self.assertEqual("1.0.0-rc.5-5935859", select(listing_type(versions), parse_constraint("1.0.0-rc.5-5935859")))
        self.assertEqual("1.0.0-rc.4", select(listing_type(versions, dist_tags={"rc": "0.45.4"}), parse_constraint("1.0-rc")))
        with self.assertRaises(ValueError):
            _ = parse_constraint("^6")


class Cli(unittest.TestCase):
    def test_npm_constraints_compat_and_dist_tags(self) -> None:
        code, snapshot, _ = run_main([
            {"name": "ts", "registry": "npm", "package": "typescript"},
            {"name": "ts6", "registry": "npm", "package": "typescript", "constraint": "6"},
            {"name": "orm", "registry": "npm", "package": "typescript", "constraint": "1.0-rc"},
        ], {"https://registry.npmjs.org/": NPM_DOC})
        self.assertEqual(0, code)
        found = {cast("str", e["name"]): e for e in entries(snapshot)}
        self.assertEqual(("7.0.2", "6.1.0", "1.0.0-rc.4"), (found["ts"]["resolved"], found["ts6"]["resolved"], found["orm"]["resolved"]))
        self.assertEqual("7.0.2", found["ts6"]["latest_stable"])
        self.assertEqual({"engines": {"node": ">=18"}, "peerDependencies": {"svelte": "^5"}}, found["ts6"]["compat"])

    def test_release_feeds(self) -> None:
        code, snapshot, _ = run_main([
            {"name": "node", "registry": "node-release"},
            {"name": "go", "registry": "go-release", "constraint": "1.26"},
            {"name": "python", "registry": "python-release", "constraint": "3.14"},
            {"name": "rust", "registry": "rust-release"},
        ], {
            "https://nodejs.org/": [{"version": "v26.1.0", "lts": False}, {"version": "v24.22.0", "lts": "Krypton"},
                                    {"version": "v22.9.0", "lts": "Jod"}],
            "https://go.dev/": [{"version": "go1.27.2", "stable": True}, {"version": "go1.26.9", "stable": True},
                                {"version": "go1.28rc1", "stable": False}],
            "https://www.python.org/": [{"name": "Python 3.15.0"}, {"name": "Python 3.14.8"}, {"name": "Python 3.14.9rc1"}],
            "https://static.rust-lang.org/": '[pkg.rust]\nversion = "1.99.1 (abc1234 2026-10-01)"\n',
        })
        self.assertEqual(0, code)
        found = {cast("str", e["name"]): e for e in entries(snapshot)}
        self.assertEqual(("v26.1.0", "v24.22.0"), (found["node"]["resolved"], found["node"]["lts"]))
        self.assertEqual(("1.26.9", "1.27.2"), (found["go"]["resolved"], found["go"]["latest_stable"]))
        self.assertEqual("3.14.8", found["python"]["resolved"])
        self.assertEqual("1.99.1", found["rust"]["resolved"])

    def test_pypi_and_crates_listing_and_compat(self) -> None:
        code, snapshot, _ = run_main([
            {"name": "py", "registry": "pypi", "package": "demo"},
            {"name": "rs", "registry": "crates", "package": "demo"},
        ], {
            "https://pypi.org/pypi/demo/1.0/json": {"info": {"requires_python": ">=3.11", "requires_dist": ["anyio>=4"]}},
            "https://pypi.org/pypi/demo/json": {"releases": {"2.0": [{"yanked": True}], "1.0": [{"yanked": False}], "3.0": []}},
            "https://crates.io/api/v1/crates/demo/1.2.0/dependencies": {"dependencies": [
                {"crate_id": "serde", "req": "^1", "kind": "normal", "optional": False}]},
            "https://crates.io/api/v1/crates/demo": {"versions": [{"num": "1.3.0", "yanked": True}, {"num": "1.2.0", "yanked": False},
                                                                   {"num": "2.0.0-beta.1", "yanked": False}]},
        })
        self.assertEqual(0, code)
        found = {cast("str", e["name"]): e for e in entries(snapshot)}
        self.assertEqual("1.0", found["py"]["resolved"])
        self.assertEqual({"requires_python": ">=3.11", "requires_dist": ["anyio>=4"]}, found["py"]["compat"])
        self.assertEqual("1.2.0", found["rs"]["resolved"])
        self.assertEqual({"dependencies": [{"crate": "serde", "req": "^1", "kind": "normal", "optional": False}]}, found["rs"]["compat"])

    def test_unresolvable_constraint_and_network_errors_exit_1(self) -> None:
        code, snapshot, stderr = run_main([
            {"name": "ts9", "registry": "npm", "package": "typescript", "constraint": "9"},
            {"name": "gone", "registry": "hex", "package": "missing"},
            {"name": "manual", "registry": None},
        ], {"https://registry.npmjs.org/": NPM_DOC})
        self.assertEqual(1, code)
        found = {cast("str", e["name"]): e for e in entries(snapshot)}
        self.assertIn("no version matching '9' found", cast("str", found["ts9"]["error"]))
        self.assertIn("unexpected URL", cast("str", found["gone"]["error"]))
        self.assertIsNone(found["manual"]["resolved"])
        self.assertIn("ts9:", stderr)

    def test_previous_snapshot_reports_changed_new_and_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path(temporary) / "versions-old.json"
            _ = previous.write_text('{"components":[{"name":"a","resolved":"6.0.1"},{"name":"legacy","latest":"0.1.0"}]}')
            code, snapshot, stderr = run_main([
                {"name": "a", "registry": "npm", "package": "typescript", "constraint": "6"},
                {"name": "b", "registry": "npm", "package": "typescript"},
            ], {"https://registry.npmjs.org/": NPM_DOC}, "--previous", str(previous))
        self.assertEqual(0, code)
        self.assertEqual([("6.0.1", "6.1.0", True), (None, "7.0.2", True)],
                         [(e["previous"], e["resolved"], e["changed"]) for e in entries(snapshot)])
        self.assertEqual(["legacy"], snapshot["removed"])
        self.assertIn("removed: legacy (was 0.1.0)", stderr)

    def test_malformed_inputs_exit_2_without_traceback(self) -> None:
        payloads: list[object] = [[{}], [{"name": [], "registry": None}], [{"name": "x", "registry": "maven", "package": "bad"}],
                                  [{"name": "x", "registry": "npm", "package": "x", "constraint": ">=6"}],
                                  [{"name": "x", "registry": "nope", "package": "x"}], {"not": "a list"}]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "components.json"
            for payload in payloads:
                with self.subTest(payload=payload):
                    _ = source.write_text(json.dumps(payload))
                    result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "registry_versions.py"), str(source)],
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    _ = unittest.main()
