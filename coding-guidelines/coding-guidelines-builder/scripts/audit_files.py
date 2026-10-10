#!/usr/bin/env python3
"""Audit a run folder against the closed file set in references/workspace.md.

Usage: audit_files.py <run-dir>

Lists every file that is not part of the allowed layout and not declared under
"## Additional files" in manifest.md, and every undeclared symlink that resolves
outside the run folder (a layout directory that is really a link elsewhere
escapes the closed set; a toolchain's link to a system interpreter is declared
like any other additional file). Symlinks are not followed. Exits 1 if any are
found. Never deletes files.
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ALLOWED = [
    "manifest.md",
    "research/components.json",
    "research/probe.md",
    "research/sources.md",
    "research/versions.json",
    "research/versions-*.json",
    "research/facts/*.md",
    "research/clones/**",
    "tasks/evals.json",
    "tasks/check.sh",
    "tasks/anti-patterns.sh",
    "tasks/*/**",
    "baseline/mistakes.md",
    "baseline/benchmark.json",
    "baseline/benchmark.md",
    "baseline/eval-*/**",
    "examples/**",
    "skill/**",
    "skill-workspace/**",
    ".toolchain/**",
]

TRANSIENT = ["research/clones/**"]  # allowed during the run, must be gone by cleanup


def declared_additional(manifest: Path) -> set[str]:
    if not manifest.exists():
        return set()
    text = manifest.read_text(encoding="utf-8")
    m = re.search(r"^## Additional files\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return set()
    paths: set[str] = set()
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        body = line.lstrip("-* ").strip()
        token = body.split()[0] if body else ""
        token = token.strip("`")
        if token:
            paths.add(token.rstrip("/"))
    return paths


def matches(rel: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        base = pattern[:-3]
        if "*" in base:
            parts = rel.split("/")
            bparts = base.split("/")
            if len(parts) <= len(bparts):
                return False
            return all(fnmatch.fnmatchcase(p, b) for p, b in zip(parts, bparts))
        return rel == base or rel.startswith(base + "/")
    return fnmatch.fnmatchcase(rel, pattern)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1].startswith("--"):
        print(__doc__)
        return 2
    run = Path(argv[1]).resolve()
    if not run.is_dir():
        print(f"not a directory: {run}", file=sys.stderr)
        return 2
    if not (run / "manifest.md").is_file():
        print("manifest.md missing", file=sys.stderr)
        return 2

    extra = declared_additional(run / "manifest.md")
    offenders: list[Path] = []
    transient: list[Path] = []
    escaped: list[Path] = []
    for path in sorted(run.rglob("*")):
        rel = path.relative_to(run).as_posix()
        if any(rel == e or rel.startswith(e + "/") for e in extra):
            continue
        if path.is_symlink() and not path.resolve().is_relative_to(run):
            escaped.append(path)
            continue
        if path.is_dir():
            continue
        if any(matches(rel, t) for t in TRANSIENT):
            transient.append(path)
            continue
        if any(matches(rel, a) for a in ALLOWED):
            continue
        offenders.append(path)

    if transient:
        print(f"{len(transient)} transient file(s) under research/clones/ (remove in phase 5)")
    for p in escaped:
        print(f"symlink escapes the run folder: {p.relative_to(run).as_posix()} -> {p.resolve()}"
              + " (replace it, or declare it under '## Additional files' in manifest.md with a reason)")
    if not offenders and not escaped:
        print("file set clean")
        return 0
    if offenders:
        print(f"{len(offenders)} file(s) outside the closed set:")
        for p in offenders:
            print(f"  {p.relative_to(run).as_posix()}")
        print("review these files, or declare each under '## Additional files' in manifest.md with a reason")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
