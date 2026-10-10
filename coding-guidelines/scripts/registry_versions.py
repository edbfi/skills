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
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

UA = "stack-skill-builder/1 (+registry version snapshot)"
PRERELEASE = re.compile(r"[-+]|(?:a|b|rc|alpha|beta|dev|pre|preview|nightly)\d*$", re.I)


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def is_stable(v: str) -> bool:
    return not PRERELEASE.search(v)


def version_key(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else -1 for p in re.split(r"[.\-+]", v))


def newest_stable(versions: list[str]) -> str | None:
    stable = [v for v in versions if is_stable(v)]
    return max(stable, key=version_key) if stable else None


def go_escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def latest(registry: str, package: str) -> str | None:
    if registry == "crates":
        d = fetch_json(f"https://crates.io/api/v1/crates/{urllib.parse.quote(package)}")
        return d["crate"].get("max_stable_version") or d["crate"].get("max_version")
    if registry == "npm":
        d = fetch_json(f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='@')}")
        return d.get("dist-tags", {}).get("latest")
    if registry == "pypi":
        d = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json")
        v = d["info"]["version"]
        return v if is_stable(v) else newest_stable(list(d.get("releases", {})))
    if registry == "go":
        d = fetch_json(f"https://proxy.golang.org/{go_escape(package)}/@latest")
        return d.get("Version")
    if registry == "rubygems":
        d = fetch_json(f"https://rubygems.org/api/v1/versions/{urllib.parse.quote(package)}/latest.json")
        return d.get("version")
    if registry == "hex":
        d = fetch_json(f"https://hex.pm/api/packages/{urllib.parse.quote(package)}")
        return d.get("latest_stable_version") or d.get("latest_version")
    if registry == "maven":
        group, _, artifact = package.partition(":")
        q = urllib.parse.quote(f'g:"{group}" AND a:"{artifact}"')
        d = fetch_json(f"https://search.maven.org/solrsearch/select?q={q}&rows=1&wt=json")
        docs = d.get("response", {}).get("docs", [])
        return docs[0].get("latestVersion") if docs else None
    if registry == "nuget":
        d = fetch_json(f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/index.json")
        return newest_stable(d.get("versions", []))
    raise ValueError(f"unsupported registry: {registry}")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    components = json.load(open(args[0], encoding="utf-8"))
    previous: dict[str, str | None] = {}
    if "--previous" in argv:
        prev_path = argv[argv.index("--previous") + 1]
        prev = json.load(open(prev_path, encoding="utf-8"))
        previous = {c["name"]: c.get("latest") for c in prev.get("components", [])}

    out = []
    failures = 0
    for c in components:
        entry = {"name": c["name"], "registry": c.get("registry"), "package": c.get("package"), "latest": None}
        if c.get("registry"):
            try:
                entry["latest"] = latest(c["registry"], c["package"])
            except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as e:
                entry["error"] = str(e)
                failures += 1
                print(f"{c['name']}: {e}", file=sys.stderr)
        else:
            entry["note"] = "no registry; fill from source tags or toolchain version command"
        if previous:
            before = previous.get(c["name"])
            entry["previous"] = before
            entry["changed"] = bool(entry["latest"]) and before != entry["latest"]
            if entry["changed"]:
                print(f"changed: {c['name']} {before} -> {entry['latest']}", file=sys.stderr)
        out.append(entry)

    json.dump({"generated": date.today().isoformat(), "components": out}, sys.stdout, indent=2)
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
