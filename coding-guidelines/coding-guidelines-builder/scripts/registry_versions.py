#!/usr/bin/env python3
"""Snapshot stable candidates from package registries for subsequent compatibility research.

Usage: registry_versions.py <components.json> [--previous <versions.json>] > versions.json

components.json entries need "name", "registry" and "package". Supported
registries: crates, npm, pypi, go, rubygems, hex, maven (package "group:artifact"),
nuget. Entries with registry null are copied through with "latest": null so the
researcher fills them from source tags or the toolchain's version command.

With --previous, the previous snapshot is compared and each changed component
is marked "changed": true and listed on stderr. A re-run uses that list to
decide which components need fresh research.

Latest tags can point at prereleases. Reject unresolved candidates instead of
claiming they are stable. Unrecognized version conventions require manual research;
this script does not resolve user constraints or cross-package compatibility.
"""
from __future__ import annotations

import json
import argparse
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from http.client import HTTPResponse
from typing import cast

UA = "coding-guidelines-builder/1 (+registry version snapshot)"
STABLE = re.compile(r"v?\d+(?:\.\d+)*(?:\.post\d+|[.-](?:Final|RELEASE))?(?:\+[0-9A-Za-z.-]+)?", re.I)


def fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    # urlopen is typed Any; for http(s) URLs it is documented to return an HTTPResponse.
    with cast("HTTPResponse", urllib.request.urlopen(req, timeout=30)) as resp:
        return cast("object", json.load(resp))


def load_json(path: str) -> object:
    with open(path, encoding="utf-8") as fh:
        try:
            return cast("object", json.load(fh))
        except ValueError as e:  # JSONDecodeError and UnicodeDecodeError name no file
            raise ValueError(f"{path}: {e}") from e


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
    return STABLE.fullmatch(v) is not None


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(match.group()) for match in re.finditer(r"\d+", v.removeprefix("v").split("+", 1)[0]))


def newest_stable(versions: list[str]) -> str | None:
    stable = [v for v in versions if is_stable(v)]
    return max(stable, key=version_key) if stable else None


def go_escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def latest(registry: str, package: str) -> str | None:
    if registry == "crates":
        crate = require(fetch_json(f"https://crates.io/api/v1/crates/{urllib.parse.quote(package)}"), "crate")
        return version(get(crate, "max_stable_version"))
    if registry == "npm":
        d = fetch_json(f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='@')}")
        return version(get(get(d, "dist-tags"), "latest"))
    if registry == "pypi":
        d = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(package)}/json")
        v = text(require(require(d, "info"), "version"))
        releases = get(d, "releases")
        release_map = cast("dict[str, object]", releases) if isinstance(releases, dict) else {}  # JSON object keys are strings
        usable = [key for key, files in release_map.items() if any(
            get(file, "yanked") is False for file in array(files) or []
        )]
        return v if is_stable(v) and v in usable else newest_stable(usable)
    if registry == "go":
        d = fetch_json(f"https://proxy.golang.org/{go_escape(package)}/@latest")
        return version(get(d, "Version"))
    if registry == "rubygems":
        d = fetch_json(f"https://rubygems.org/api/v1/versions/{urllib.parse.quote(package)}/latest.json")
        return version(get(d, "version"))
    if registry == "hex":
        d = fetch_json(f"https://hex.pm/api/packages/{urllib.parse.quote(package)}")
        return version(get(d, "latest_stable_version"))
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


class Arguments(argparse.Namespace):
    components: str = ""
    previous: str | None = None


def component_entries(value: object) -> list[object]:
    entries = array(value)
    if entries is None:
        raise ValueError("expected a JSON array of components")
    names: set[str] = set()
    for entry in entries:
        name = text(require(entry, "name"))
        if not name.strip() or name in names:
            raise ValueError(f"empty or duplicate component name: {name!r}")
        names.add(name)
        registry = require(entry, "registry")
        if registry is not None:
            if text(registry) not in {"crates", "npm", "pypi", "go", "rubygems", "hex", "maven", "nuget"}:
                raise ValueError(f"unsupported registry: {registry}")
            package = text(require(entry, "package"))
            if not package.strip() or (registry == "maven" and not re.fullmatch(r"[^:]+:[^:]+", package)):
                raise ValueError(f"invalid package: {package!r}")
    return entries


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("components")
    _ = parser.add_argument("--previous")
    args = parser.parse_args(argv[1:], namespace=Arguments())
    prev_path = args.previous
    try:
        components = component_entries(load_json(args.components))
        previous_entries = component_entries(require(load_json(prev_path), "components")) if prev_path else []
    except (OSError, ValueError, KeyError) as e:
        print(f"cannot read input: {e}", file=sys.stderr)
        return 2
    previous = {text(require(c, "name")): get(c, "latest") for c in previous_entries}

    out: list[dict[str, object]] = []
    failures = 0
    for c in components:
        name = text(require(c, "name"))
        registry = get(c, "registry")
        entry: dict[str, object] = {"name": name, "registry": registry, "package": get(c, "package"), "latest": None}
        if registry:
            try:
                candidate = latest(text(registry), text(require(c, "package")))
                if candidate is None or not is_stable(candidate):
                    raise ValueError(f"no verified stable candidate ({candidate!r}); research official release metadata")
                entry["latest"] = candidate
            except (OSError, KeyError, ValueError) as e:  # OSError covers URLError and read timeouts
                entry["error"] = str(e)
                failures += 1
                print(f"{name}: {e}", file=sys.stderr)
        else:
            entry["note"] = "no registry; fill from source tags or toolchain version command"
        if prev_path:
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
