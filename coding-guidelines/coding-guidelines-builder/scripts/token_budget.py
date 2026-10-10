#!/usr/bin/env python3
"""Report approximate token counts for the generated skill against its budgets.

Usage: token_budget.py <skill-dir> [--json]

Tokens are a rough characters / 4 estimate, not a tokenizer measurement.
Descriptions must be a single-line YAML scalar, as required by this repository.

Budgets (aim / ceiling): SKILL.md 2000 / 3000; each references/*.md 4000 / 6000.
The description is reported separately (ceiling ~1000 characters). Exits 1 if
any ceiling is exceeded.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TypedDict

BUDGETS = {"SKILL.md": (2000, 3000), "reference": (4000, 6000)}
DESC_CEILING_CHARS = 1000


class FileRow(TypedDict):
    file: str
    tokens: int
    aim: int
    ceiling: int
    lines: int


class DescriptionRow(TypedDict):
    file: str
    tokens: int
    chars: int
    ceiling_chars: int


def estimate(text: str) -> int:
    return round(len(text) / 4)


def description_of(skill_md: str) -> str:
    m = re.match(r"^---\s*\n(.*?)\n---", skill_md, re.S)
    if not m:
        raise ValueError("YAML frontmatter missing")
    d = re.search(r"^description:[ \t]*(.*)$", m.group(1), re.M)
    if not d or not d.group(1).strip():
        raise ValueError("description missing")
    value = d.group(1).strip()
    if value.startswith((">", "|")) or (value[0] in "\"'" and not value.endswith(value[0])):
        raise ValueError("description must be a single-line YAML scalar")
    for line in m.group(1)[d.end():].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", line):
            break
        raise ValueError("description must be a single-line YAML scalar")
    return value.strip('"\'')


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    skill = Path(args[0])
    as_json = "--json" in argv
    files: list[FileRow] = []
    over = 0

    skill_md = skill / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        aim, ceil = BUDGETS["SKILL.md"]
        t = estimate(text)
        files.append({"file": "SKILL.md", "tokens": t, "aim": aim, "ceiling": ceil, "lines": text.count("\n") + 1})
        over += t > ceil
        try:
            desc = description_of(text)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        description: DescriptionRow = {"file": "description", "tokens": estimate(desc), "chars": len(desc), "ceiling_chars": DESC_CEILING_CHARS}
        over += len(desc) > DESC_CEILING_CHARS
    else:
        print("SKILL.md missing", file=sys.stderr)
        return 1

    for ref in sorted((skill / "references").glob("*.md")):
        text = ref.read_text(encoding="utf-8")
        aim, ceil = BUDGETS["reference"]
        t = estimate(text)
        files.append({"file": f"references/{ref.name}", "tokens": t, "aim": aim, "ceiling": ceil, "lines": text.count("\n") + 1})
        over += t > ceil

    total = sum(r["tokens"] for r in files)
    if as_json:
        rows = [files[0], description, *files[1:]]
        print(json.dumps({"rows": rows, "total_tokens": total, "over_ceiling": over}, indent=2))
    else:
        print(f"{'file':<36}{'tokens':>8}{'aim':>8}{'ceiling':>9}{'lines':>7}")
        for index, r in enumerate(files):
            flag = " OVER" if r["tokens"] > r["ceiling"] else (" high" if r["tokens"] > r["aim"] else "")
            print(f"{r['file']:<36}{r['tokens']:>8}{r['aim']:>8}{r['ceiling']:>9}{r['lines']:>7}{flag}")
            if index == 0:  # the description row follows SKILL.md
                flag = " OVER" if description["chars"] > DESC_CEILING_CHARS else ""
                print(f"{'description':<36}{description['tokens']:>8}{'':>8}{description['ceiling_chars']:>8}c{'':>7}{flag}")
        print(f"{'total (loaded files)':<36}{total:>8}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
