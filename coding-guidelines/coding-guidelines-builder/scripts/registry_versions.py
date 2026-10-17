#!/usr/bin/env python3
"""Resolve component versions from registries and release feeds, with compatibility data.

Usage: registry_versions.py <components.json> [--previous <versions.json>] > versions.json

components.json is a JSON array. Each entry has "name", "registry" and, for package
registries, "package"; "constraint" is optional:

  {"name": "typescript", "registry": "npm", "package": "typescript", "constraint": "6"}

Registries: crates, npm, pypi, go (module proxy), rubygems, hex, maven (package
"group:artifact"), nuget. Release feeds for toolchains without a package registry:
go-release, node-release, python-release, rust-release (no package needed). rust-release reads
the stable channel manifest, which names only the current stable release: a constraint on an older
Rust line (such as "1.85") fails and is resolved from the Rust release notes instead, confirmed with
`rustc --version` in the pinned image. Entries with registry null are copied through with
"resolved": null for manual research.

Constraints (references/pack-format.md, "Version resolution"):
  none          newest stable release
  "6"           newest stable 6.x          "6.0"     newest stable 6.0.x
  "6.0.3"       exactly 6.0.3              "1.0-rc"  newest 1.0 rc prerelease
  "1.0.0-rc.5-5935859"  exactly that prerelease build
A prerelease line prefers the registry dist-tag of the same name (npm) and otherwise takes
the highest prerelease of that tag, skipping builds with a commit or date suffix.

Each output entry has "resolved", "latest_stable", and "compat": the declared peer, engine
or interpreter ranges of the resolved version (npm peerDependencies, peerDependenciesMeta and
engines; PyPI requires_python and requires_dist; crates dependency requirements), or null
where the source publishes none. node-release adds "lts" (newest LTS release). The builder
interprets ranges; this script only reports them.

With --previous, each component is compared with the earlier snapshot's resolved version and
marked "changed"; components only in the earlier snapshot are listed under "removed". Errors
are reported per component and make the exit status 1; unreadable input exits 2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from http.client import HTTPResponse
from typing import cast

UA = "coding-guidelines-builder/2 (+registry version resolution)"
PACKAGE_REGISTRIES = frozenset({"crates", "npm", "pypi", "go", "rubygems", "hex", "maven", "nuget"})
RELEASE_FEEDS = frozenset({"go-release", "node-release", "python-release", "rust-release"})
STABLE_SUFFIX = re.compile(r"(?i)\.post\d+|[.-](?:final|release|ga)")
CONSTRAINT = re.compile(r"(?P<nums>\d+(?:\.\d+)*)(?:-(?P<pre>[0-9A-Za-z][0-9A-Za-z.-]*))?")
TAG_ALIASES = {"a": "alpha", "b": "beta", "c": "rc", "pre": "preview"}


# --- version model ---

@dataclass(frozen=True)
class Version:
    raw: str
    release: tuple[int, ...]
    pre: tuple[str, ...] | None  # None for a stable release
    suffixed: bool  # a prerelease carrying a commit hash, date stamp or extra build part

    @property
    def tag(self) -> str | None:
        if not self.pre:
            return None
        first = self.pre[0].lower()
        return TAG_ALIASES.get(first, first) if first.isalpha() else None

    def key(self) -> tuple[tuple[int, ...], int, tuple[tuple[int, int, str], ...]]:
        padded = self.release + (0,) * (6 - len(self.release))
        if self.pre is None:
            return padded, 1, ()
        return padded, 0, tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in self.pre)


def parse_version(raw: str) -> Version | None:
    cleaned = raw.strip().removeprefix("v").split("+", 1)[0]
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(.*)", cleaned)
    if not match:
        return None
    release = tuple(int(part) for part in match[1].split("."))
    rest = match[2]
    if not rest or STABLE_SUFFIX.fullmatch(rest):
        return Version(raw, release, None, False)
    body = rest.lstrip(".-")
    if not body or not re.fullmatch(r"[0-9A-Za-z.-]+", body):
        return None
    identifiers: list[str] = []
    for part in re.split(r"[.-]", body):
        identifiers.extend(re.findall(r"[A-Za-z]+|\d+", part))
    if not identifiers:
        return None
    hashlike = any(len(p) >= 7 and (p.isdigit() or (re.fullmatch(r"[0-9a-f]+", p) is not None and re.search(r"[a-f]", p) is not None))
                   for p in identifiers)
    # "rc.5-5935859": a hyphen after the numbered tag introduces a build suffix.
    extra_part = re.fullmatch(r"[A-Za-z]+\.?\d+-.+", body) is not None
    return Version(raw, release, tuple(identifiers), hashlike or extra_part)


def is_stable(raw: str) -> bool:
    version = parse_version(raw)
    return version is not None and version.pre is None


@dataclass(frozen=True)
class Constraint:
    raw: str
    prefix: tuple[int, ...]
    pre_tag: str | None = None  # "rc": newest of that prerelease tag
    pre_exact: str | None = None  # an exact prerelease build


def parse_constraint(raw: str) -> Constraint:
    match = CONSTRAINT.fullmatch(raw.strip().removeprefix("v"))
    if not match:
        raise ValueError(f"invalid constraint {raw!r}; use 6, 6.0, 6.0.3, 1.0-rc or an exact prerelease")
    prefix = tuple(int(part) for part in match["nums"].split("."))
    pre = match["pre"]
    if pre is None:
        return Constraint(raw, prefix)
    if pre.isalpha():
        return Constraint(raw, prefix, pre_tag=TAG_ALIASES.get(pre.lower(), pre.lower()))
    return Constraint(raw, prefix, pre_exact=f"{match['nums']}-{pre}")


def padded(release: tuple[int, ...], length: int = 6) -> tuple[int, ...]:
    return release + (0,) * max(0, length - len(release))


def in_line(version: Version, prefix: tuple[int, ...]) -> bool:
    return padded(version.release, len(prefix))[: len(prefix)] == prefix


@dataclass
class Listing:
    versions: list[str]
    dist_tags: dict[str, str] = field(default_factory=dict)
    lts: list[str] = field(default_factory=list)
    documents: dict[str, object] = field(default_factory=dict)  # per-version metadata when the listing has it


def newest(candidates: list[Version]) -> Version | None:
    return max(candidates, key=Version.key) if candidates else None


def select(found: Listing, constraint: Constraint | None) -> str | None:
    parsed = [v for v in (parse_version(raw) for raw in found.versions) if v is not None]
    if constraint is None:
        best = newest([v for v in parsed if v.pre is None])
        return best.raw if best else None
    line = [v for v in parsed if in_line(v, constraint.prefix)]
    if constraint.pre_exact is not None:
        wanted = constraint.pre_exact
        return next((v.raw for v in line if v.raw.removeprefix("v").split("+", 1)[0] == wanted), None)
    if constraint.pre_tag is not None:
        tagged = found.dist_tags.get(constraint.pre_tag)
        tagged_version = parse_version(tagged) if tagged else None
        if tagged_version is not None and tagged_version.pre is not None and in_line(tagged_version, constraint.prefix):
            return tagged_version.raw
        best = newest([v for v in line if v.tag == constraint.pre_tag and not v.suffixed])
        return best.raw if best else None
    stable = [v for v in line if v.pre is None]
    if len(constraint.prefix) >= 3:
        return next((v.raw for v in stable if padded(v.release) == padded(constraint.prefix)), None)
    best = newest(stable)
    return best.raw if best else None


# --- fetching (tests patch fetch_text) ---

def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    # urlopen is typed Any; for http(s) URLs it is documented to return an HTTPResponse.
    with cast("HTTPResponse", urllib.request.urlopen(req, timeout=30)) as resp:
        return resp.read().decode("utf-8")


def fetch_json(url: str) -> object:
    return cast("object", json.loads(fetch_text(url)))


def get(value: object, key: str) -> object:
    """``value.get(key)`` on a parsed JSON object; None for any other JSON value."""
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value).get(key)  # JSON object keys are always strings


def require(value: object, key: str) -> object:
    """``value[key]`` on a parsed JSON object; KeyError like the lookup it replaces."""
    if isinstance(value, dict):
        entries = cast("dict[str, object]", value)  # JSON object keys are always strings
        if key in entries:
            return entries[key]
    raise KeyError(key)


def array(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def members(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {value!r}")
    return value


def strings(values: list[object]) -> list[str]:
    return [v for v in values if isinstance(v, str)]


def go_escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def listing(registry: str, package: str) -> Listing:
    quoted = urllib.parse.quote(package, safe="")
    if registry == "crates":
        crate = fetch_json(f"https://crates.io/api/v1/crates/{quoted}")
        return Listing(strings([get(v, "num") for v in array(get(crate, "versions")) if get(v, "yanked") is not True]))
    if registry == "npm":
        doc = fetch_json(f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='@')}")
        published = members(get(doc, "versions"))
        tags = {k: v for k, v in members(get(doc, "dist-tags")).items() if isinstance(v, str)}
        return Listing(list(published), dist_tags=tags, documents=published)
    if registry == "pypi":
        doc = fetch_json(f"https://pypi.org/pypi/{quoted}/json")
        releases = members(get(doc, "releases"))
        return Listing([v for v, files in releases.items() if any(get(f, "yanked") is False for f in array(files))])
    if registry == "go":
        body = fetch_text(f"https://proxy.golang.org/{go_escape(package)}/@v/list")
        return Listing([line.strip() for line in body.splitlines() if line.strip()])
    if registry == "rubygems":
        doc = fetch_json(f"https://rubygems.org/api/v1/versions/{quoted}.json")
        return Listing(strings([get(v, "number") for v in array(doc)]))
    if registry == "hex":
        doc = fetch_json(f"https://hex.pm/api/packages/{quoted}")
        return Listing(strings([get(v, "version") for v in array(get(doc, "releases"))]))
    if registry == "maven":
        group, _, artifact = package.partition(":")
        q = urllib.parse.quote(f'g:"{group}" AND a:"{artifact}"')
        doc = fetch_json(f"https://search.maven.org/solrsearch/select?q={q}&core=gav&rows=200&wt=json")
        return Listing(strings([get(d, "v") for d in array(get(get(doc, "response"), "docs"))]))
    if registry == "nuget":
        doc = fetch_json(f"https://api.nuget.org/v3-flatcontainer/{package.lower()}/index.json")
        return Listing(strings(array(get(doc, "versions"))))
    if registry == "go-release":
        doc = fetch_json("https://go.dev/dl/?mode=json&include=all")
        return Listing([v.removeprefix("go") for v in strings([get(r, "version") for r in array(doc)])])
    if registry == "node-release":
        releases = array(fetch_json("https://nodejs.org/dist/index.json"))
        lts = strings([get(r, "version") for r in releases if isinstance(get(r, "lts"), str)])
        return Listing(strings([get(r, "version") for r in releases]), lts=lts)
    if registry == "python-release":
        names = strings([get(r, "name") for r in array(fetch_json("https://www.python.org/api/v2/downloads/release/?is_published=true"))])
        return Listing([m[1] for m in (re.fullmatch(r"Python (\S+)", n) for n in names) if m])
    if registry == "rust-release":
        channel = tomllib.loads(fetch_text("https://static.rust-lang.org/dist/channel-rust-stable.toml"))
        stamped = text(require(require(require(channel, "pkg"), "rust"), "version"))
        return Listing([stamped.split()[0]])
    raise ValueError(f"unsupported registry: {registry}")


def published(ranges: dict[str, object]) -> dict[str, object] | None:
    """The declared ranges with absent or empty entries dropped; None when nothing is declared."""
    kept = {k: v for k, v in ranges.items() if v is not None and v != [] and v != {}}
    return kept or None


def compat(registry: str, package: str, resolved: str, found: Listing) -> dict[str, object] | None:
    quoted = urllib.parse.quote(package, safe="")
    version = urllib.parse.quote(resolved, safe="")
    if registry == "npm":
        doc = found.documents.get(resolved)
        return published({k: get(doc, k) for k in ("peerDependencies", "peerDependenciesMeta", "engines")})
    if registry == "pypi":
        info = get(fetch_json(f"https://pypi.org/pypi/{quoted}/{version}/json"), "info")
        return published({"requires_python": get(info, "requires_python"), "requires_dist": get(info, "requires_dist")})
    if registry == "crates":
        deps = fetch_json(f"https://crates.io/api/v1/crates/{quoted}/{version}/dependencies")
        return published({"dependencies": [
            {"crate": get(d, "crate_id"), "req": get(d, "req"), "kind": get(d, "kind"), "optional": get(d, "optional")}
            for d in array(get(deps, "dependencies"))
        ]})
    return None


# --- CLI ---

class Arguments(argparse.Namespace):
    components: str = ""
    previous: str | None = None


def load_json(path: str) -> object:
    with open(path, encoding="utf-8") as fh:
        try:
            return cast("object", json.load(fh))
        except ValueError as e:  # JSONDecodeError and UnicodeDecodeError name no file
            raise ValueError(f"{path}: {e}") from e


def component_entries(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("expected a JSON array of components")
    entries = cast("list[object]", value)
    names: set[str] = set()
    for entry in entries:
        name = text(require(entry, "name"))
        if not name.strip() or name in names:
            raise ValueError(f"empty or duplicate component name: {name!r}")
        names.add(name)
        registry = require(entry, "registry")
        if registry is not None:
            if text(registry) not in PACKAGE_REGISTRIES | RELEASE_FEEDS:
                raise ValueError(f"unsupported registry: {registry}")
            if registry in PACKAGE_REGISTRIES:
                package = text(require(entry, "package"))
                if not package.strip() or (registry == "maven" and not re.fullmatch(r"[^:]+:[^:]+", package)):
                    raise ValueError(f"invalid package: {package!r}")
        constraint = get(entry, "constraint")
        if constraint is not None:
            _ = parse_constraint(text(constraint))
    return entries


def resolve(entry: object) -> tuple[dict[str, object], str | None]:
    name = text(require(entry, "name"))
    registry = get(entry, "registry")
    package = get(entry, "package")
    raw_constraint = get(entry, "constraint")
    out: dict[str, object] = {"name": name, "registry": registry, "package": package,
                              "constraint": raw_constraint, "resolved": None, "latest_stable": None, "compat": None}
    if registry is None:
        out["note"] = "no registry or feed; resolve from official release metadata and the toolchain's version command"
        return out, None
    package_name = package if isinstance(package, str) else ""
    try:
        constraint = parse_constraint(text(raw_constraint)) if raw_constraint is not None else None
        found = listing(text(registry), package_name)
        out["latest_stable"] = select(found, None)
        if found.lts:
            lts = newest([v for v in (parse_version(r) for r in found.lts) if v is not None and v.pre is None])
            out["lts"] = lts.raw if lts else None
        resolved = select(found, constraint)
        if resolved is None:
            wanted = f"version matching {constraint.raw!r}" if constraint else "stable version"
            raise ValueError(f"no {wanted} found; research official release metadata")
        out["resolved"] = resolved
        out["compat"] = compat(text(registry), package_name, resolved, found)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as e:  # OSError covers URLError and timeouts
        out["error"] = str(e)
        return out, f"{name}: {e}"
    return out, None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("components")
    _ = parser.add_argument("--previous")
    args = parser.parse_args(argv[1:], namespace=Arguments())
    prev_path = args.previous
    try:
        components = component_entries(load_json(args.components))
        previous_entries = array(require(load_json(prev_path), "components")) if prev_path else []
        previous = {text(require(c, "name")): get(c, "resolved") or get(c, "latest") for c in previous_entries}
    except (OSError, ValueError, KeyError) as e:
        print(f"cannot read input: {e}", file=sys.stderr)
        return 2

    out: list[dict[str, object]] = []
    failures = 0
    for component in components:
        entry, error = resolve(component)
        if error:
            failures += 1
            print(error, file=sys.stderr)
        if prev_path:
            before = previous.get(text(entry["name"]))
            entry["previous"] = before
            changed = bool(entry["resolved"]) and before != entry["resolved"]
            entry["changed"] = changed
            if changed:
                print(f"changed: {entry['name']} {before} -> {entry['resolved']}", file=sys.stderr)
        out.append(entry)

    snapshot: dict[str, object] = {"generated": date.today().isoformat(), "components": out}
    if prev_path:
        removed = sorted(set(previous) - {text(require(c, "name")) for c in components})
        snapshot["removed"] = removed
        for name in removed:
            print(f"removed: {name} (was {previous[name]})", file=sys.stderr)
    json.dump(snapshot, sys.stdout, indent=2)
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
