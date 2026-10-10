#!/usr/bin/env python3
"""Snapshot the latest stable version of every component from its package registry.

Usage: registry_versions.py <components.json> [--previous <versions.json>] > versions.json

components.json entries need "name", "registry" and "package". Supported
registries: crates, npm, pypi, go, rubygems, hex, maven (package "group:artifact"),
nuget. Entries with registry null are copied through with "latest": null so the
researcher fills them from source tags or the toolchain's version command.

With --previous, the previous snapshot is compared and each changed component
is marked "changed": true and listed on stderr. A re-run uses that list to
decide which components need fresh research.

Stable means no pre-release suffix as the registry defines it; where a registry
exposes a "latest stable" field it is used directly.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from http.client import HTTPResponse
from typing import cast

UA = "coding-guidelines-builder/1 (+registry version snapshot)"
PRERELEASE = re.compile(r"[-+]|(?:a|b|rc|alpha|beta|dev|pre|preview|nightly)\d*$", re.I)


def fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    # urlopen is typed Any; for http(s) URLs it is documented to return an HTTPResponse.
    with cast("HTTPResponse", urllib.request.urlopen(req, timeout=30)) as resp:
        return cast("object", json.load(resp))


def load_json(path: str) -> object:
    with open(path, encoding="utf-8") as fh:
        return cast("object", json.load(fh))


def get(value: object, key: str) -> object:
    """``value.get(key)`` on a parsed JSON object; None for any other JSON value."""
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value).get(key)  # JSON object keys are always strings


def require(value: object, key: str) -> object:
    """``value[key]`` on a parsed JSON object; KeyError like the lookup it replaces."""
    if isinstance(value, dict):
        members = cast("dict[str, object]", value)  # JSON object keys are always strings
        if key in members:
            return members[key]
    raise KeyError(key)


def array(value: object) -> list[object] | None:
    """The items of a parsed JSON array; None for any other JSON value."""
    return cast("list[object]", value) if isinstance(value, list) else None


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {value!r}")
    return value


def version(value: object) -> str | None:
    return value if isinstance(value, str) else None


def is_stable(v: str) -> bool:
    return not PRERELEASE.search(v)


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else -1 for p in re.split(r"[.\-+]", v))


def newest_stable(versions: list[str]) -> str | None:
    stable = [v for v in versions if is_stable(v)]
    return max(stable, key=version_key) if stable else None


def go_escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def latest(registry: str, package: str) -> str | None:
    if registry == "crates":
        crate = require(fetch_json(f"https://crates.io/api/v1/crates/{urllib.parse.quote(package)}"), "crate")
        return version(get(crate, "max_stable_version")) or version(get(crate, "max_version"))
    if registry == "npm":
        d = fetch_json(f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='@')}")
        return version(get(get(d, "dist-tags"), "latest"))
    if registry == "pypi":
        d = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json")
        v = text(require(require(d, "info"), "version"))
        releases = get(d, "releases")
        keys = list(cast("dict[str, object]", releases)) if isinstance(releases, dict) else []  # JSON object keys are always strings
        return v if is_stable(v) else newest_stable(keys)
    if registry == "go":
        d = fetch_json(f"https://proxy.golang.org/{go_escape(package)}/@latest")
        return version(get(d, "Version"))
    if registry == "rubygems":
        d = fetch_json(f"https://rubygems.org/api/v1/versions/{urllib.parse.quote(package)}/latest.json")
        return version(get(d, "version"))
    if registry == "hex":
        d = fetch_json(f"https://hex.pm/api/packages/{urllib.parse.quote(package)}")
        return version(get(d, "latest_stable_version")) or version(get(d, "latest_version"))
    if registry == "maven":
        group, _, artifact = package.partition(":")
        q = urllib.parse.quote(f'g:"{group}" AND a:"{artifact}"')
        d = fetch_json(f"https://search.maven.org/solrsearch/select?q={q}&rows=1&wt=json")
        docs = array(get(get(d, "response"), "docs")) or []
        return version(get(docs[0], "latestVersion")) if docs else None
    if registry == "nuget":
        d = fetch_json(f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/index.json")
        return newest_stable([v for v in array(get(d, "versions")) or [] if isinstance(v, str)])
    raise ValueError(f"unsupported registry: {registry}")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    components = array(load_json(args[0]))
    if components is None:
        print(f"{args[0]}: expected a JSON array of components", file=sys.stderr)
        return 2
    previous: dict[object, object] = {}
    if "--previous" in argv:
        prev_path = argv[argv.index("--previous") + 1]
        prev = load_json(prev_path)
        previous = {require(c, "name"): get(c, "latest") for c in array(get(prev, "components")) or []}

    out: list[dict[str, object]] = []
    failures = 0
    for c in components:
        name = require(c, "name")
        registry = get(c, "registry")
        entry: dict[str, object] = {"name": name, "registry": registry, "package": get(c, "package"), "latest": None}
        if registry:
            try:
                entry["latest"] = latest(text(registry), text(require(c, "package")))
            except (OSError, KeyError, ValueError) as e:  # OSError covers URLError and read timeouts
                entry["error"] = str(e)
                failures += 1
                print(f"{name}: {e}", file=sys.stderr)
        else:
            entry["note"] = "no registry; fill from source tags or toolchain version command"
        if previous:
            before = previous.get(name)
            entry["previous"] = before
            changed = bool(entry["latest"]) and before != entry["latest"]
            entry["changed"] = changed
            if changed:
                print(f"changed: {name} {before} -> {entry['latest']}", file=sys.stderr)
        out.append(entry)

    json.dump({"generated": date.today().isoformat(), "components": out}, sys.stdout, indent=2)
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
