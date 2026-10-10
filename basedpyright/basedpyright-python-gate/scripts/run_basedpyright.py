"""Run ``uvx basedpyright@latest`` and print its diagnostics grouped by rule.

The raw checker output is a flat list sorted by file, which invites fixing
symptoms one line at a time. Grouping by rule, worst first, makes the real
question visible: *where does the untyped value enter?* One fix at that
source usually clears a whole group.

Usage::

    python run_basedpyright.py                       # summary, up to 8 lines per rule
    python run_basedpyright.py --limit 20            # wider sample per rule
    python run_basedpyright.py --rule reportAny      # every diagnostic for one rule
    python run_basedpyright.py --raw-json out.json   # also keep the raw checker output
    python run_basedpyright.py -- src/pkg/mod.py     # extra args go to basedpyright

Exit codes: 0 when the checker reports 0 errors and 0 warnings, 1 when it
reports any, 2 when it could not be run. Informational diagnostics are shown
but never fail the run. Runs on Python 3.11+; must itself pass the gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import cast

CHECKER = ("uvx", "basedpyright@latest", "--outputjson")
NO_RULE = "<no rule>"
MESSAGE_WIDTH = 160


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int
    column: int
    severity: str
    rule: str
    message: str

    def render(self, root: Path, full: bool) -> str:
        path = Path(self.file)
        try:
            shown = str(path.relative_to(root))
        except ValueError:
            shown = self.file
        lines = self.message.splitlines() or [""]
        if full:
            text = "\n      ".join(lines)
        else:
            text = lines[0]
            if len(text) > MESSAGE_WIDTH:
                text = text[: MESSAGE_WIDTH - 1] + "…"
        return f"{shown}:{self.line}:{self.column}  {text}"


def find_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return None


def as_dict(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def as_str(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def parse_diagnostics(payload: dict[str, object]) -> list[Diagnostic]:
    raw = payload.get("generalDiagnostics")
    if not isinstance(raw, list):
        return []
    out: list[Diagnostic] = []
    for item in cast("list[object]", raw):
        entry = as_dict(item)
        start = as_dict(as_dict(entry.get("range")).get("start"))
        out.append(
            Diagnostic(
                file=as_str(entry.get("file")),
                line=as_int(start.get("line")) + 1,
                column=as_int(start.get("character")) + 1,
                severity=as_str(entry.get("severity"), "error"),
                rule=as_str(entry.get("rule"), NO_RULE),
                message=as_str(entry.get("message")),
            )
        )
    return out


def run_checker(root: Path, extra: list[str]) -> tuple[dict[str, object], str] | None:
    """Return (parsed JSON, raw stdout), or None when the checker could not run."""
    try:
        result = subprocess.run(
            [*CHECKER, *extra],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print("run_basedpyright: `uvx` not found on PATH — install uv first", file=sys.stderr)
        return None
    stdout = result.stdout
    # basedpyright prints the JSON document to stdout; anything else
    # (version notices, uv progress) lands on stderr or before the JSON.
    brace = stdout.find("{")
    if brace < 0:
        print("run_basedpyright: checker produced no JSON output", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        return None
    try:
        parsed = cast("object", json.loads(stdout[brace:]))
    except json.JSONDecodeError as exc:
        print(f"run_basedpyright: could not parse checker output: {exc}", file=sys.stderr)
        print(stdout[-2000:], file=sys.stderr)
        return None
    return as_dict(parsed), stdout


def print_report(
    root: Path,
    payload: dict[str, object],
    diagnostics: list[Diagnostic],
    limit: int,
    only_rule: str | None,
) -> None:
    summary = as_dict(payload.get("summary"))
    errors = as_int(summary.get("errorCount"))
    warnings = as_int(summary.get("warningCount"))
    infos = as_int(summary.get("informationCount"))
    files = as_int(summary.get("filesAnalyzed"))
    version = as_str(payload.get("version"), "?")
    print(
        f"basedpyright {version}: {errors} errors / {warnings} warnings / "
        + f"{infos} informations in {files} files"
    )
    if not diagnostics:
        return

    by_rule: defaultdict[str, list[Diagnostic]] = defaultdict(list)
    for diag in diagnostics:
        by_rule[diag.rule].append(diag)

    if only_rule is not None:
        group = by_rule.get(only_rule, [])
        print(f"\n{only_rule}  {len(group)}")
        if not group:
            print("  (no diagnostics for this rule; check the spelling)")
        for diag in group:
            print(f"  {diag.render(root, full=True)}")
        return

    ranked = sorted(by_rule.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for rule, group in ranked:
        severities = Counter(diag.severity for diag in group)
        detail = ", ".join(f"{count} {sev}" for sev, count in sorted(severities.items()))
        print(f"\n{rule}  {len(group)}  ({detail})")
        for diag in group[:limit]:
            print(f"  {diag.render(root, full=False)}")
        hidden = len(group) - limit
        if hidden > 0:
            print(f"  … +{hidden} more  (--rule {rule} shows all)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    _ = parser.add_argument("--root", type=Path, default=Path.cwd())
    _ = parser.add_argument("--limit", type=int, default=8, help="lines shown per rule")
    _ = parser.add_argument("--rule", help="show every diagnostic for this one rule")
    _ = parser.add_argument("--raw-json", type=Path, help="write the raw checker JSON here")
    _ = parser.add_argument("extra", nargs="*", help="arguments passed through to basedpyright")
    args = parser.parse_args(argv)

    start = cast("Path", args.root).resolve()
    limit = max(1, cast("int", args.limit))
    only_rule = cast("str | None", args.rule)
    raw_json = cast("Path | None", args.raw_json)
    extra = cast("list[str]", args.extra)

    root = find_root(start)
    if root is None:
        print(f"run_basedpyright: no pyproject.toml found from {start} upward", file=sys.stderr)
        return 2

    outcome = run_checker(root, extra)
    if outcome is None:
        return 2
    payload, stdout = outcome
    if raw_json is not None:
        _ = raw_json.write_text(stdout, encoding="utf-8")

    diagnostics = parse_diagnostics(payload)
    print_report(root, payload, diagnostics, limit, only_rule)

    summary = as_dict(payload.get("summary"))
    failing = as_int(summary.get("errorCount")) + as_int(summary.get("warningCount"))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
