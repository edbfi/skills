#!/usr/bin/env python3
"""Enforce the admission rule: no section without evidence, no anti-pattern without a grep.

Usage: check_provenance.py <skill-dir>

Reads <skill-dir>/PROVENANCE.md, whose "## Evidence" table has the columns
file | section | evidence | reference, and checks:

- every ATX H2 and H3 heading (`##`, `###`; setext underlines are not
  recognized) in SKILL.md and references/*.md has a row whose file and section
  match (case-insensitive, whitespace-normalized); a loaded file with no H2 or
  H3 needs one row whose section is its H1 title or `*`;
- every evidence value is one of baseline, probe, decision, compat, or structure,
  with a nonempty reference; `structure` is accepted only for the fixed layout
  sections of SKILL.md (Decisions, Top mistakes, Check, Routing) and a Contents
  table of contents;
- every row points at a heading that still exists (stale rows are reported);
- every data row of the wrong / why / right / grep table in
  references/anti-patterns.md has a non-empty grep column. The table is found
  by its header, wherever it sits in the file.

Table rows must start with `|`, and a literal pipe inside a cell is written as a backslash-escaped pipe.

Exits 1 on any structural failure. Evidence support must be audited separately.
Frontmatter and headings inside code fences are ignored.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EVIDENCE = {"baseline", "probe", "decision", "compat", "structure"}
STRUCTURE_SECTIONS = {"decisions", "top mistakes", "check", "routing"}  # SKILL.md only; "contents" anywhere


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().strip("`").lower())


def headings(md: Path) -> tuple[str, list[str]]:
    """The H1 title (or "") and the H2/H3 headings outside frontmatter and code fences."""
    title = ""
    found: list[str] = []
    fence_marker = ""
    fence_length = 0
    in_front = False
    for i, line in enumerate(md.read_text(encoding="utf-8-sig").splitlines()):
        if i == 0 and line.strip() == "---":
            in_front = True
            continue
        if in_front:
            if line.strip() == "---":
                in_front = False
            continue
        fence = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            marker, rest = fence.groups()
            if not fence_marker:
                fence_marker, fence_length = marker[0], len(marker)
            elif marker[0] == fence_marker and len(marker) >= fence_length and not rest.strip():
                fence_marker = ""
            continue
        if fence_marker:
            continue
        m = re.match(r"^(#|##|###)\s+(.+?)(?:\s+#+)?\s*$", line)
        if m and m.group(1) == "#":
            title = title or m.group(2)
        elif m:
            found.append(m.group(2))
    return title, found


def structural(file: str, section: str) -> bool:
    return section == "contents" or (file == "skill.md" and section in STRUCTURE_SECTIONS)


def cells_of(line: str) -> list[str]:
    """Cells of a table line, split on unescaped pipes so grep alternation like `a\\|b` stays one cell."""
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def find_table(text: str, columns: list[str]) -> list[list[str]] | None:
    """Data rows of the first table whose header is exactly `columns`; None when there is none."""
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        if not line.strip().startswith("|") or [norm(c) for c in cells_of(line)] != columns:
            continue
        separator = cells_of(lines[index + 1])
        if len(separator) != len(columns) or not all(re.fullmatch(r":?-{2,}:?", c) for c in separator):
            continue
        rows: list[list[str]] = []
        for row in lines[index + 2:]:
            if not row.strip().startswith("|"):
                break
            rows.append(cells_of(row))
        return rows
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    skill = Path(argv[1])
    if not (skill / "SKILL.md").is_file():
        print("SKILL.md missing")
        return 1
    prov = skill / "PROVENANCE.md"
    if not prov.is_file():
        print("PROVENANCE.md missing")
        return 1
    provenance = prov.read_text(encoding="utf-8-sig")
    evidence_section = re.search(r"^## Evidence\s*$(.*?)(?=^## |\Z)", provenance, re.M | re.S)
    rows = find_table(evidence_section.group(1), ["file", "section", "evidence", "reference"]) if evidence_section else None
    if rows is None:
        print("Evidence table missing or malformed")
        return 1
    covered: set[tuple[str, str]] = set()
    failures = 0
    for r in rows:
        if len(r) != 4 or any(not norm(cell) for cell in r):
            print(f"malformed evidence row: {r}")
            failures += 1
            continue
        file, section, evidence = r[0].strip("`"), r[1], r[2].lower()
        if evidence not in EVIDENCE:
            print(f"{file} / {section}: evidence '{r[2]}' not in {sorted(EVIDENCE)}")
            failures += 1
        elif evidence == "structure" and not structural(norm(file), norm(section)):
            print(f"{file} / {section}: 'structure' is only for SKILL.md {sorted(STRUCTURE_SECTIONS)} or a Contents list")
            failures += 1
        covered.add((norm(file), norm(section)))

    actual: set[tuple[str, str]] = set()
    files = [skill / "SKILL.md"] + sorted((skill / "references").glob("*.md"))
    for md in files:
        if not md.is_file():
            continue
        rel = md.relative_to(skill).as_posix()
        title, sections = headings(md)
        if not sections:
            file_keys = {(norm(rel), "*"), (norm(rel), norm(title))} - {(norm(rel), "")}
            actual |= file_keys
            if not file_keys & covered:
                print(f"{rel}: no sections and no file-level evidence row (section '*' or '{title}')")
                failures += 1
            continue
        for h in sections:
            key = (norm(rel), norm(h))
            actual.add(key)
            if key not in covered:
                print(f"{rel}: '{h}' has no evidence row")
                failures += 1
    for key in sorted(covered - actual):
        print(f"stale evidence row: {key[0]} / {key[1]} (heading not found)")
        failures += 1

    anti = skill / "references" / "anti-patterns.md"
    if anti.is_file():
        anti_rows = find_table(anti.read_text(encoding="utf-8-sig"), ["wrong", "why", "right", "grep"])
        if anti_rows is None:
            print("anti-patterns.md: wrong / why / right / grep table missing or malformed")
            failures += 1
        for r in anti_rows or []:
            if len(r) != 4:
                print(f"anti-patterns.md: expected 4 cells, got {len(r)} (escape pipes as \\|): {r[0][:60] if r else r}")
                failures += 1
            elif any(not norm(cell) for cell in r):
                print(f"anti-patterns.md: row without grep: {r[0][:60]}")
                failures += 1
    else:
        print("references/anti-patterns.md missing")
        failures += 1

    print("provenance clean" if not failures else f"{failures} provenance failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
