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

where the file contains lines with `region: create_order` and
`endregion: create_order` (any comment syntax; only the words matter). The
block must equal the file or region exactly, after stripping trailing
whitespace on each line.

Default mode reports every mismatch, every marker whose file or region is
missing, and every code block with no marker (a warning: config fragments and
shell commands may legitimately have none, but a block teaching a pattern
should). Exits 1 on mismatches or missing sources. With --sync, rewrites
mismatched blocks from the examples, which is the only sanctioned way to edit
a block: examples/ is the source of truth.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MARKER = re.compile(r"^\s*<!--\s*example:\s*(?P<ref>[^\s]+)\s*-->\s*$")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


def load_source(examples: Path, ref: str) -> tuple[str | None, str]:
    path_part, _, region = ref.partition("#")
    file = examples / path_part
    if not file.is_file():
        return None, f"missing file {path_part}"
    lines = file.read_text(encoding="utf-8").splitlines()
    if not region:
        # Region markers are navigation for this script, not content to teach.
        kept = [l for l in lines if not re.search(r"\b(?:end)?region:\s*\S+", l)]
        return "\n".join(l.rstrip() for l in kept), ""
    start = end = None
    for i, line in enumerate(lines):
        if re.search(rf"\bregion:\s*{re.escape(region)}\b", line) and "endregion" not in line:
            start = i
        elif re.search(rf"\bendregion:\s*{re.escape(region)}\b", line):
            end = i
            break
    if start is None or end is None or end <= start:
        return None, f"region {region} not found in {path_part}"
    body = lines[start + 1 : end]
    # Drop common leading indentation so a nested region reads cleanly.
    indents = [len(l) - len(l.lstrip()) for l in body if l.strip()]
    cut = min(indents) if indents else 0
    return "\n".join(l[cut:].rstrip() for l in body), ""


def process_file(md: Path, examples: Path, sync: bool) -> tuple[int, int, int]:
    """Returns (mismatches, missing, unmarked)."""
    lines = md.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    mismatches = missing = unmarked = 0
    i = 0
    pending_ref: str | None = None
    while i < len(lines):
        line = lines[i]
        m = MARKER.match(line)
        if m:
            pending_ref = m.group("ref")
            out.append(line)
            i += 1
            continue
        f = FENCE.match(line)
        if f:
            fence = f.group("fence")
            indent = f.group("indent")
            j = i + 1
            while j < len(lines) and not re.match(rf"^\s*{re.escape(fence)}\s*$", lines[j]):
                j += 1
            block = [l[len(indent):] if l.startswith(indent) else l for l in lines[i + 1 : j]]
            block_text = "\n".join(l.rstrip() for l in block)
            if pending_ref is None:
                unmarked += 1
                out.extend(lines[i : j + 1])
            else:
                src, err = load_source(examples, pending_ref)
                if src is None:
                    missing += 1
                    print(f"{md.name}: {pending_ref}: {err}")
                    out.extend(lines[i : j + 1])
                elif src != block_text:
                    mismatches += 1
                    if sync:
                        out.append(line)
                        out.extend(indent + l for l in src.splitlines())
                        out.append(lines[j] if j < len(lines) else indent + fence)
                        print(f"{md.name}: {pending_ref}: synced")
                    else:
                        print(f"{md.name}: {pending_ref}: differs from examples")
                        out.extend(lines[i : j + 1])
                else:
                    out.extend(lines[i : j + 1])
            pending_ref = None
            i = j + 1
            continue
        if line.strip():
            pending_ref = None  # a marker applies only to the next fence
        out.append(line)
        i += 1
    if sync and mismatches:
        _ = md.write_text("\n".join(out) + "\n", encoding="utf-8")
    return mismatches, missing, unmarked


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    skill, examples = Path(args[0]), Path(args[1])
    sync = "--sync" in argv
    files = [skill / "SKILL.md"] + sorted((skill / "references").glob("*.md"))
    totals = [0, 0, 0]
    for md in files:
        if md.is_file():
            r = process_file(md, examples, sync)
            totals = [a + b for a, b in zip(totals, r)]
    mismatches, missing, unmarked = totals
    print(f"mismatched: {mismatches}  missing sources: {missing}  unmarked blocks: {unmarked}")
    if sync:
        return 1 if missing else 0
    return 1 if (mismatches or missing) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
