#!/usr/bin/env python3
"""Enforce the admission rule: no section without evidence, no anti-pattern without a grep.

Usage: check_provenance.py <skill-dir>

Reads <skill-dir>/PROVENANCE.md, whose "## Evidence" table has the columns
file | section | evidence | reference, and checks:

- every H2 and H3 heading in SKILL.md and references/*.md has a row whose
  file and section match (case-insensitive, whitespace-normalized);
- every evidence value is one of baseline, probe, decision, compat, with a nonempty reference;
- every row points at a heading that still exists (stale rows are reported);
- every data row of the table in references/anti-patterns.md has a non-empty
  fourth (grep) column.

Exits 1 on any structural failure. Evidence support must be audited separately.
Frontmatter and headings inside code fences are ignored.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

EVIDENCE = {"baseline", "probe", "decision", "compat"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().strip("`").lower())


def headings(md: Path) -> list[str]:
    found: list[str] = []
    fence_marker = ""
    fence_length = 0
    in_front = False
    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines()):
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
        m = re.match(r"^(##|###)\s+(.+?)\s*#*\s*$", line)
        if m:
            found.append(m.group(2))
    return found


def table_rows(text: str, heading: str | None) -> list[list[str]]:
    """Rows of the first Markdown table under `heading` (or the first table if None)."""
    if heading:
        m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not m:
            return []
        text = m.group(1)
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("|"):
            # Split on unescaped pipes only, so grep alternation like `foo\|bar` stays one cell.
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                in_table = True
                continue
            if in_table:
                rows.append(cells)
        elif in_table and line.strip() == "":
            break
    return rows


def has_table(text: str, columns: list[str]) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        cells = [norm(c) for c in line.strip().strip("|").split("|")]
        separator = [c.strip() for c in lines[index + 1].strip().strip("|").split("|")]
        if cells == columns and len(separator) == len(columns) and all(
            re.fullmatch(r":?-{2,}:?", cell) for cell in separator
        ):
            return True
    return False


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
    provenance = prov.read_text(encoding="utf-8")
    evidence_section = re.search(r"^## Evidence\s*$(.*?)(?=^## |\Z)", provenance, re.M | re.S)
    if not evidence_section or not has_table(evidence_section.group(1), ["file", "section", "evidence", "reference"]):
        print("Evidence table missing or malformed")
        return 1
    rows = table_rows(provenance, "Evidence")
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
        covered.add((norm(file), norm(section)))

    actual: set[tuple[str, str]] = set()
    files = [skill / "SKILL.md"] + sorted((skill / "references").glob("*.md"))
    for md in files:
        if not md.is_file():
            continue
        rel = md.relative_to(skill).as_posix()
        for h in headings(md):
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
        anti_text = anti.read_text(encoding="utf-8")
        if not has_table(anti_text, ["wrong", "why", "right", "grep"]):
            print("anti-patterns.md: wrong / why / right / grep table missing or malformed")
            failures += 1
        for r in table_rows(anti_text, None):
            if len(r) != 4 or any(not norm(cell) for cell in r):
                print(f"anti-patterns.md: row without grep: {r[0][:60] if r else r}")
                failures += 1
    else:
        print("references/anti-patterns.md missing")
        failures += 1

    print("provenance clean" if not failures else f"{failures} provenance failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
