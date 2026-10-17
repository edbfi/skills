#!/usr/bin/env python3
"""Keep code blocks in a guidelines pack identical to files in its examples project.

Usage: verify_examples.py <pack-dir> [--examples <dir>] [--sync] [--json]

Every Markdown file in the pack outside examples/ is checked; examples default to
<pack-dir>/examples. A code block is tied to its source by an HTML comment on the
line before the opening fence:

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
blocks. Some blocks cannot be files of a passing project and are exempt by
position: a block whose info string is a shell or text language (sh, bash, zsh,
fish, shell, console, powershell, pwsh, cmd, bat, text), any unmarked block in
changes.md (old-API snippets), and an anti-pattern's wrong code (a block right
after a line starting with **Don't:**). Any other non-executable illustration
needs an explicit exemption comment:
    <!-- example-exempt: reason -->
Exemptions are counted and reported for manual review; --json prints the counts
to record in pack.json. With --sync, rewrites
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
import json
import sys
from dataclasses import dataclass
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
SHELL_INFOS = frozenset({"sh", "bash", "zsh", "fish", "shell", "console", "powershell", "pwsh", "cmd", "bat", "text"})
WRONG_CODE = re.compile(r"^\*\*Don't:\*\*")


@dataclass
class Counts:
    mismatches: int = 0
    unresolved: int = 0
    unmarked: int = 0
    verified: int = 0
    exempt_positional: int = 0
    exempt_explicit: int = 0

    def add(self, other: Counts) -> None:
        self.mismatches += other.mismatches
        self.unresolved += other.unresolved
        self.unmarked += other.unmarked
        self.verified += other.verified
        self.exempt_positional += other.exempt_positional
        self.exempt_explicit += other.exempt_explicit


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


def process_file(md: Path, examples: Path, sync: bool, label: str, changes_file: bool = False) -> Counts:
    lines = md.read_text(encoding="utf-8-sig").splitlines()
    out: list[str] = []
    synced: list[str] = []
    counts = Counts()
    i = 0
    pending_ref: str | None = None
    exempt_reason: str | None = None
    previous = ""  # the last non-blank line before the current one
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
            print(f"{label}:{i + 1}: unsupported Markdown code/container indentation; use standalone fences")
            counts.unresolved += 1
            pending_ref = exempt_reason = None
            out.append(line)
            previous = line
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
                print(f"{label}:{i + 1}: unclosed code fence")
                counts.unresolved += 1
                out.extend(lines[i:])
                break
            block = [l[len(indent):] if l.startswith(indent) else l for l in lines[i + 1 : j]]
            block_text = "\n".join(l.rstrip() for l in block)
            info = f.group("info").strip().split(maxsplit=1)[0].lower() if f.group("info").strip() else ""
            if exempt_reason:
                print(f"{label}:{i + 1}: exempt: {exempt_reason}")
                counts.exempt_explicit += 1
                out.extend(lines[i : j + 1])
            elif pending_ref is None:
                if info in SHELL_INFOS or changes_file or WRONG_CODE.match(previous):
                    counts.exempt_positional += 1
                else:
                    print(f"{label}:{i + 1}: unmarked code block; add an example marker or move it to examples/")
                    counts.unmarked += 1
                out.extend(lines[i : j + 1])
            else:
                src, err = load_source(examples, pending_ref)
                if src is None:
                    counts.unresolved += 1
                    print(f"{label}: {pending_ref}: {err}")
                    out.extend(lines[i : j + 1])
                elif src != block_text:
                    counts.mismatches += 1
                    wide = widen_fence(fence, src)
                    if sync:
                        out.append(indent + wide + f.group("info"))
                        out.extend(indent + l if l else l for l in src.splitlines())
                        out.append(indent + wide)
                        synced.append(pending_ref + (" (fence widened)" if wide != fence else ""))
                    else:
                        hint = "; the source contains a fence of this length, widen the fence" if wide != fence else ""
                        print(f"{label}: {pending_ref}: differs from examples{hint}")
                        out.extend(lines[i : j + 1])
                else:
                    counts.verified += 1
                    out.extend(lines[i : j + 1])
            pending_ref = None
            exempt_reason = None
            previous = lines[j]
            i = j + 1
            continue
        if line.strip():
            pending_ref = None  # a marker applies only to the next fence
            exempt_reason = None
            previous = line
        out.append(line)
        i += 1
    if in_frontmatter:
        print(f"{label}: unclosed frontmatter")
        counts.unresolved += 1
    if sync and counts.mismatches and not counts.unresolved and not counts.unmarked:
        _ = md.write_text("\n".join(out) + "\n", encoding="utf-8")
        for ref in synced:
            print(f"{label}: {ref}: synced")
    elif synced:
        for ref in synced:
            print(f"{label}: {ref}: not written ({counts.unresolved} unresolved, {counts.unmarked} unmarked block(s) in this file)")
    return counts


def pack_documents(pack: Path, examples: Path) -> list[Path]:
    skip = {examples.resolve(), (pack / "examples").resolve()}
    return sorted(md for md in pack.rglob("*.md")
                  if md.is_file() and not any(md.resolve().is_relative_to(s) for s in skip))


class Arguments(argparse.Namespace):
    pack: Path = Path()
    examples: Path | None = None
    sync: bool = False
    json: bool = False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("pack", type=Path)
    _ = parser.add_argument("--examples", type=Path)
    _ = parser.add_argument("--sync", action="store_true")
    _ = parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:], namespace=Arguments())
    pack = args.pack
    examples = args.examples if args.examples is not None else pack / "examples"
    if not (pack / "README.md").is_file() or not examples.is_dir():
        print("the pack needs README.md and an examples directory", file=sys.stderr)
        return 2
    totals = Counts()
    for md in pack_documents(pack, examples):
        rel = md.relative_to(pack).as_posix()
        totals.add(process_file(md, examples, args.sync, rel, changes_file=rel == "changes.md"))
    print(f"mismatched: {totals.mismatches}  unresolved blocks: {totals.unresolved}  unmarked blocks: {totals.unmarked}  "
          + f"verified: {totals.verified}  exempt: {totals.exempt_positional} positional, {totals.exempt_explicit} explicit")
    if args.json:
        blocks = {"verified": totals.verified, "exempt_positional": totals.exempt_positional, "exempt_explicit": totals.exempt_explicit}
        print(json.dumps({"blocks": blocks}))
    if args.sync:
        return 1 if (totals.unresolved or totals.unmarked) else 0
    return 1 if (totals.mismatches or totals.unresolved or totals.unmarked) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
