#!/usr/bin/env python3
"""Keep code blocks in the skill identical to files in the examples project.

Usage: verify_examples.py <skill-dir> <examples-dir> [--sync]

A code block in SKILL.md or references/*.md is tied to its source by an HTML
comment on the line before the opening fence:

    <!-- example: src/handlers.rs -->
    ```rust
    ...
    ```

or, for part of a file, a named region:

    <!-- example: src/handlers.rs#create_order -->

where the file contains comment lines whose whole content is
`region: create_order` and `endregion: create_order` (any comment leader:
`//`, `#`, `--`, `;`, `/* */`, `<!-- -->`, ...; in Markdown, reStructuredText
and plain-text sources only `<!-- -->`, so a heading is never a marker). A line
that merely contains the word `region:` inside code or data is not a marker.
Marker lines are navigation, not content: a full-file block omits them and
reports how many it omitted, and a region block omits nested markers. The block
must equal the file or region exactly, after stripping trailing whitespace on
each line.

Default mode fails on mismatches, unresolved blocks (missing sources, duplicate
region names, malformed fences, unsupported Markdown containers), and unmarked
blocks. Non-executable illustration can use an explicit exemption comment:
    <!-- example-exempt: reason -->
Exemptions are reported for manual review. With --sync, rewrites
mismatched blocks from the examples, which is the only sanctioned way to edit
a block: examples/ is the source of truth. Sync widens a block's fence when the
source itself contains a fence of the same character and length, so the block
stays closed. Each Markdown file is rewritten independently and only when all
of its blocks resolve; the file is written with LF line endings and no BOM.

Generated Markdown must use standalone fenced blocks with at most three leading
spaces. Blockquoted/list-prefixed fences and unfenced indented code are rejected;
normalize them to standalone fences before verification or synchronization.
"""
from __future__ import annotations

import re
import argparse
import sys
from pathlib import Path

MARKER = re.compile(r"^\s*<!--\s*example:\s*(?P<ref>[^\s]+)\s*-->\s*$")
# A region marker is a whole comment line: an optional closer follows the name.
REGION = re.compile(
    r"^\s*(?P<leader>//+|#+|--+|;+|/\*+|<!--|\*+|%+|'+|\(\*|\{-|REM\b)\s*(?P<end>end)?region:\s*(?P<name>\S+?)\s*(?:\*/|-->|\*\)|-\})?\s*$"
)
PROSE_SUFFIXES = {".md", ".markdown", ".rst", ".txt"}
EXEMPT = re.compile(r"^\s*<!--\s*example-exempt:\s*(\S.*?)\s*-->\s*$")
FENCE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
CONTAINER_FENCE = re.compile(r"^(?:[ \t]*(?:>|[-+*]|\d+[.)])[ \t]*)+[`~]{3,}")


def region_marker(line: str, prose: bool = False) -> tuple[bool, str] | None:
    """(is_end, name) when the line is a region marker comment, else None."""
    m = REGION.match(line)
    if not m or (prose and m.group("leader") != "<!--"):
        return None
    return (m.group("end") is not None, m.group("name"))


def widen_fence(fence: str, source: str) -> str:
    """The shortest fence of the same character that `source` cannot close."""
    runs = re.finditer(rf"^ {{0,3}}({re.escape(fence[0])}{{3,}})", source, re.M)
    longest = max((len(m.group(1)) for m in runs), default=0)
    return fence[0] * max(len(fence), longest + 1)


def load_source(examples: Path, ref: str) -> tuple[str | None, str]:
    path_part, _, region = ref.partition("#")
    file = (examples / path_part).resolve()
    if not path_part or Path(path_part).is_absolute() or not file.is_relative_to(examples.resolve()):
        return None, f"source escapes examples directory: {path_part}"
    if not file.is_file():
        return None, f"missing file {path_part}"
    lines = file.read_text(encoding="utf-8-sig").splitlines()
    prose = file.suffix.lower() in PROSE_SUFFIXES
    if not region:
        # Region markers are navigation for this script, not content to teach.
        kept = [l for l in lines if region_marker(l, prose) is None]
        if len(kept) != len(lines):
            print(f"{ref}: omitted {len(lines) - len(kept)} region marker line(s)")
        return "\n".join(l.rstrip() for l in kept), ""
    markers = [(i, region_marker(line, prose)) for i, line in enumerate(lines)]
    starts = [i for i, m in markers if m == (False, region)]
    if len(starts) > 1:
        return None, f"region {region} starts twice in {path_part}"
    start = starts[0] if starts else None
    end = next((i for i, m in markers if m == (True, region) and start is not None and i > start), None)
    if start is None or end is None:
        return None, f"region {region} not found in {path_part}"
    body = [l for l in lines[start + 1 : end] if region_marker(l, prose) is None]
    # Drop common leading indentation so a nested region reads cleanly.
    indents = [len(l) - len(l.lstrip()) for l in body if l.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(l[cut:].rstrip() for l in body), ""


def process_file(md: Path, examples: Path, sync: bool) -> tuple[int, int, int]:
    """Returns (mismatches, unresolved, unmarked)."""
    lines = md.read_text(encoding="utf-8-sig").splitlines()
    out: list[str] = []
    synced: list[str] = []
    mismatches = unresolved = unmarked = 0
    i = 0
    pending_ref: str | None = None
    exempt_reason: str | None = None
    in_frontmatter = False
    while i < len(lines):
        line = lines[i]
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            out.append(line)
            i += 1
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            out.append(line)
            i += 1
            continue
        if CONTAINER_FENCE.match(line) or (line.strip() and re.match(r"^(?: {4}|\t)", line)):
            print(f"{md.name}:{i + 1}: unsupported Markdown code/container indentation; use standalone fences")
            unresolved += 1
            pending_ref = exempt_reason = None
            out.append(line)
            i += 1
            continue
        m = MARKER.match(line)
        if m:
            pending_ref = m.group("ref")
            exempt_reason = None
            out.append(line)
            i += 1
            continue
        exemption = EXEMPT.match(line)
        if exemption:
            pending_ref = None
            exempt_reason = exemption.group(1)
            out.append(line)
            i += 1
            continue
        f = FENCE.match(line)
        if f:
            fence = f.group("fence")
            indent = f.group("indent")
            j = i + 1
            closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*$")
            while j < len(lines) and not closing.match(lines[j]):
                j += 1
            if j == len(lines):
                print(f"{md.name}:{i + 1}: unclosed code fence")
                unresolved += 1
                out.extend(lines[i:])
                break
            block = [l[len(indent):] if l.startswith(indent) else l for l in lines[i + 1 : j]]
            block_text = "\n".join(l.rstrip() for l in block)
            if exempt_reason:
                print(f"{md.name}:{i + 1}: exempt: {exempt_reason}")
                out.extend(lines[i : j + 1])
            elif pending_ref is None:
                unmarked += 1
                out.extend(lines[i : j + 1])
            else:
                src, err = load_source(examples, pending_ref)
                if src is None:
                    unresolved += 1
                    print(f"{md.name}: {pending_ref}: {err}")
                    out.extend(lines[i : j + 1])
                elif src != block_text:
                    mismatches += 1
                    wide = widen_fence(fence, src)
                    if sync:
                        out.append(indent + wide + f.group("info"))
                        out.extend(indent + l if l else l for l in src.splitlines())
                        out.append(indent + wide)
                        synced.append(pending_ref + (" (fence widened)" if wide != fence else ""))
                    else:
                        hint = "; the source contains a fence of this length, widen the fence" if wide != fence else ""
                        print(f"{md.name}: {pending_ref}: differs from examples{hint}")
                        out.extend(lines[i : j + 1])
                else:
                    out.extend(lines[i : j + 1])
            pending_ref = None
            exempt_reason = None
            i = j + 1
            continue
        if line.strip():
            pending_ref = None  # a marker applies only to the next fence
            exempt_reason = None
        out.append(line)
        i += 1
    if in_frontmatter:
        print(f"{md.name}: unclosed frontmatter")
        unresolved += 1
    if sync and mismatches and not unresolved and not unmarked:
        _ = md.write_text("\n".join(out) + "\n", encoding="utf-8")
        for ref in synced:
            print(f"{md.name}: {ref}: synced")
    elif synced:
        for ref in synced:
            print(f"{md.name}: {ref}: not written ({unresolved} unresolved, {unmarked} unmarked block(s) in this file)")
    return mismatches, unresolved, unmarked


class Arguments(argparse.Namespace):
    skill: Path = Path()
    examples: Path = Path()
    sync: bool = False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("skill", type=Path)
    _ = parser.add_argument("examples", type=Path)
    _ = parser.add_argument("--sync", action="store_true")
    args = parser.parse_args(argv[1:], namespace=Arguments())
    skill, examples, sync = args.skill, args.examples, args.sync
    if not (skill / "SKILL.md").is_file() or not examples.is_dir():
        print("SKILL.md and examples directory must exist", file=sys.stderr)
        return 2
    files = [skill / "SKILL.md"] + sorted((skill / "references").glob("*.md"))
    totals = [0, 0, 0]
    for md in files:
        if md.is_file():
            r = process_file(md, examples, sync)
            totals = [a + b for a, b in zip(totals, r)]
    mismatches, unresolved, unmarked = totals
    print(f"mismatched: {mismatches}  unresolved blocks: {unresolved}  unmarked blocks: {unmarked}")
    if sync:
        return 1 if (unresolved or unmarked) else 0
    return 1 if (mismatches or unresolved or unmarked) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
