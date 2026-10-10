#!/usr/bin/env python3
"""Run workspace helper for let-vps-scout.

  init     create a run folder with ledger CSVs, report template and fonts
  merge    upsert fenced ```csv <table>``` blocks from worker files into the ledger
  upsert   set fields on one ledger row
  summary  print coverage counters and the verified ranking
  publish  validate report.html and write one self-contained file to the archive

Standard library only. Only the coordinator runs merge, upsert and publish.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import io
import os
import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, cast

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
TEMPLATE = ASSETS / "report-template.html"
DEFAULT_BASE = Path(os.environ.get("LET_VPS_WORKDIR", "/tmp/let-vps"))
DEFAULT_ARCHIVE = Path(os.environ.get("LET_VPS_ARCHIVE", "~/Documents/Research/LET-VPS")).expanduser()

# table -> (primary key, columns)
TABLES: dict[str, tuple[str, list[str]]] = {
    "assignments": ("id", ["id", "type", "scope", "owner", "pages", "status", "created", "updated", "output", "notes"]),
    "batches": ("batch_id", ["batch_id", "listing_pages", "status", "completed_at", "cheapest", "six_vcpu", "upgrades", "changed", "reason"]),
    "listings": ("page", ["page", "url", "captured_at", "thread_ids", "overlap_note"]),
    "threads": ("discussion_id", ["discussion_id", "title", "url", "listing_pages", "sticky", "total_pages", "pages_read", "provider_ids", "status", "notes"]),
    "providers": ("provider_id", ["provider_id", "name", "website", "thread_ids", "coupons", "assignment", "status", "outcome", "reason", "checked_at"]),
    "candidates": ("candidate_id", [
        "candidate_id", "provider_id", "plan", "location", "country", "state",
        "vcpu", "cpu_sharing", "cpu_model", "ram_gb", "disk", "connectivity",
        "billing_term", "currency", "first_year_total", "renewal_total", "setup_fee", "mandatory_extras",
        "coupon", "coupon_recurs", "first_year_eur", "renewal_eur", "monthly_eur",
        "payment_methods", "crypto", "payment_fees", "port_speed", "transfer",
        "game_policy", "cpu_policy", "stock", "verified_at",
        "product_url", "order_url", "let_source", "evidence", "notes",
    ]),
    "gaps": ("gap_id", ["gap_id", "kind", "subject", "detail", "recorded_at", "resolved"]),
    "fx": ("currency", ["currency", "eur_per_unit", "rate_date", "source_url", "captured_at"]),
}
# Multi-value cells: merged as an ordered union instead of overwritten.
LIST_COLUMNS = {"thread_ids", "listing_pages", "pages_read", "provider_ids", "coupons", "payment_methods", "evidence"}
CANDIDATE_STATES = {"provisional", "shortlisted", "verified", "blocked", "unavailable", "excluded"}
BROWSERS = ("ego-browser", "agent-browser")

BLOCK_RE = re.compile(r"^```csv[ \t]+([a-z]+)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
SLOT_RE = re.compile(r"<!-- (/?)slot:([a-z-]+) -->")
LOCKED_RE = re.compile(r"<(style|script)\b[^>]*>(.*?)</\1>", re.S | re.I)
FONT_URL_RE = re.compile(r"""url\((["']?)fonts/([A-Za-z0-9._-]+\.woff2)\1\)""")
EXTERNAL_RE = re.compile(r"""<(?:link|script|img|iframe|source|video|audio)\b[^>]*\b(?:src|href)=["']?(?:https?:)?//""", re.I)

STATUS_TEMPLATE = """# let-vps-scout run {run_id}

- State: running
- Working folder: {run}
- Archive: {archive}
- Browser backend: {browser}
- Browser handle: {handle}
- Last checkpoint: {now}

## Counters

Run `python3 {script} summary {run}` and paste the counters here at each checkpoint.

## Stopping rule

- Current batch: listing pages 1-20
- Unchanged completed batches: 0/2

## Recommendations

- Cheapest verified annual plan: none yet
- Best inexpensive 6+ vCPU option: none yet
- Highlighted upgrades: none yet

## Active assignments

None.

## Blockers

None.

## Resume point

Open listing page 1: https://lowendtalk.com/categories/offers

## Session log

- {now}: run created
"""


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"error: {message}")


def table_path(run: Path, table: str) -> Path:
    return run / "ledger" / f"{table}.csv"


def read_table(run: Path, table: str) -> dict[str, dict[str, str]]:
    key, columns = TABLES[table]
    path = table_path(run, table)
    if not path.is_file():
        fail(f"{path} is missing; is {run} a run folder?")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            fail(f"{path} header differs from the schema")
        return {row[key]: row for row in reader}


def write_table(run: Path, table: str, rows: dict[str, dict[str, str]]) -> None:
    columns = TABLES[table][1]
    path = table_path(run, table)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{table}.", suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, quoting=csv.QUOTE_ALL, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows.values())
    os.replace(tmp, path)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def apply(rows: dict[str, dict[str, str]], table: str, incoming: dict[str, str]) -> str:
    """Upsert one row. Blank incoming cells keep existing values: blank means not checked."""
    key, columns = TABLES[table]
    unknown = set(incoming) - set(columns)
    if unknown:
        fail(f"{table}: unknown columns {sorted(unknown)}")
    ident = (incoming.get(key) or "").strip()
    if not ident:
        fail(f"{table}: row without {key}")
    if table == "candidates" and incoming.get("state") and incoming["state"].strip() not in CANDIDATE_STATES:
        fail(f"candidates {ident}: state must be one of {sorted(CANDIDATE_STATES)}")
    existing = rows.get(ident)
    row = existing or {column: "" for column in columns}
    for column, raw in incoming.items():
        value = (raw or "").strip()
        if not value:
            continue
        if column in LIST_COLUMNS and row[column]:
            merged = split_list(row[column])
            merged += [item for item in split_list(value) if item not in merged]
            row[column] = "; ".join(merged)
        else:
            row[column] = value
    rows[ident] = row
    return "updated" if existing else "added"


# Each cmd_* reads its options with cast(): argparse produced them from the parser in main().
def cmd_init(args: argparse.Namespace) -> None:
    base = Path(cast("str", args.base)).expanduser()
    archive = Path(cast("str", args.archive)).expanduser()
    base.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    run = Path(tempfile.mkdtemp(prefix=f"{stamp}_", dir=base))
    for sub in ("ledger", "workers", "evidence/listings", "evidence/threads", "evidence/providers", "evidence/screenshots", "fonts"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        write_table(run, table, {})
    _ = (run / "report.html").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    for font in (ASSETS / "fonts").glob("*.woff2"):
        _ = (run / "fonts" / font.name).write_bytes(font.read_bytes())
    browser = cast("str", args.browser)
    if browser == "agent-browser":
        # The whole random suffix keeps session names unique per run; it may itself contain "_".
        host = f"letvps-{run.name.removeprefix(f'{stamp}_')}"
        handle = f"host session `{host}`, CDP URL not recorded yet; workers use `{host}-<assignment>`"
    else:
        handle = "TaskSpace ID not recorded yet"
    _ = (run / "STATUS.md").write_text(
        STATUS_TEMPLATE.format(
            run_id=run.name, run=run, archive=archive, browser=browser, handle=handle,
            now=now(), script=Path(__file__).resolve(),
        ),
        encoding="utf-8",
    )
    print(run)


def cmd_merge(args: argparse.Namespace) -> None:
    run = Path(cast("str", args.run))
    files = cast("list[str]", args.files)
    dry_run = cast("bool", args.dry_run)
    loaded: dict[str, dict[str, dict[str, str]]] = {}
    counts: dict[tuple[str, str], int] = {}
    for name in files:
        text = Path(name).read_text(encoding="utf-8")
        blocks = [(match[1], match[2]) for match in BLOCK_RE.finditer(text)]
        if not blocks:
            print(f"warning: {name} has no ```csv <table>``` blocks", file=sys.stderr)
        for table, body in blocks:
            if table not in TABLES:
                fail(f"{name}: unknown table {table!r}")
            rows = loaded.setdefault(table, read_table(run, table))
            for incoming in csv.DictReader(io.StringIO(body)):
                if None in incoming:
                    fail(f"{name}: {table} row has more cells than its header: {incoming[None]}")
                result = apply(rows, table, incoming)
                counts[(table, result)] = counts.get((table, result), 0) + 1
    if not dry_run:
        for table, rows in loaded.items():
            write_table(run, table, rows)
    for (table, result), count in sorted(counts.items()):
        print(f"{table}: {count} {result}")
    if dry_run:
        print("dry run: ledger unchanged")


def cmd_upsert(args: argparse.Namespace) -> None:
    run = Path(cast("str", args.run))
    table = cast("str", args.table)
    ident = cast("str", args.key)
    fields = cast("list[str]", args.fields)
    if table not in TABLES:
        fail(f"unknown table {table!r}")
    key = TABLES[table][0]
    incoming = {key: ident}
    for pair in fields:
        column, sep, value = pair.partition("=")
        if not sep:
            fail(f"expected column=value, got {pair!r}")
        incoming[column] = value
    if "updated" in TABLES[table][1] and "updated" not in incoming:
        incoming["updated"] = now()
    rows = read_table(run, table)
    print(f"{table} {ident}: {apply(rows, table, incoming)}")
    write_table(run, table, rows)


def tally(rows: dict[str, dict[str, str]], column: str) -> str:
    counts: dict[str, int] = {}
    for row in rows.values():
        label = row[column] or "blank"
        counts[label] = counts.get(label, 0) + 1
    return ", ".join(f"{label} {count}" for label, count in sorted(counts.items())) or "none"


def as_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return float("inf")


def cmd_summary(args: argparse.Namespace) -> None:
    run = Path(cast("str", args.run))
    top = cast("int", args.top)
    t = {table: read_table(run, table) for table in TABLES}
    pages = sorted(int(p) for p in t["listings"] if p.isdigit())
    comment_pages = sum(len(split_list(row["pages_read"])) for row in t["threads"].values())
    open_gaps = {k: v for k, v in t["gaps"].items() if v["resolved"].lower() not in {"yes", "true", "resolved"}}
    print(f"- Listing pages: {len(pages)} captured" + (f" (pages {pages[0]}-{pages[-1]})" if pages else ""))
    print(f"- Threads: {len(t['threads'])} unique ({tally(t['threads'], 'status')}); comment pages read: {comment_pages}")
    print(f"- Providers: {len(t['providers'])} ({tally(t['providers'], 'status')}); outcomes: {tally(t['providers'], 'outcome')}")
    print(f"- Candidates: {len(t['candidates'])} ({tally(t['candidates'], 'state')})")
    print(f"- Assignments: {tally(t['assignments'], 'status')}")
    print(f"- Open gaps: {len(open_gaps)} ({tally(open_gaps, 'kind')})")
    for batch in t["batches"].values():
        print(f"- Batch {batch['batch_id']} ({batch['listing_pages']}): {batch['status']}, changed={batch['changed'] or '?'}")
    verified = [c for c in t["candidates"].values() if c["state"] == "verified"]
    annual = sorted((c for c in verified if c["billing_term"] == "annual" and c["connectivity"] in {"", "ipv4"}), key=lambda c: as_float(c["first_year_eur"]))
    if annual:
        print("\nVerified annual plans with public IPv4, cheapest first:")
        for rank, c in enumerate(annual[:top], 1):
            print(f"{rank}. {c['candidate_id']}: {c['plan']} ({c['location']}) {c['vcpu']} vCPU/{c['ram_gb']} GB, EUR {c['first_year_eur']} first year, renewal {c['renewal_eur'] or 'unknown'}")
        six = next((c for c in annual if as_float(c["vcpu"]) >= 6), None)
        if six:
            print(f"Cheapest verified 6+ vCPU: {six['candidate_id']} at EUR {six['first_year_eur']}")


def locked_blocks(html: str) -> list[tuple[str, str]]:
    return [(match[1].lower(), match[2].strip()) for match in LOCKED_RE.finditer(html)]


def slots(html: str) -> list[tuple[str, str]]:
    return [(match[1], match[2]) for match in SLOT_RE.finditer(html)]


def cmd_publish(args: argparse.Namespace) -> None:
    run = Path(cast("str", args.run))
    archive = Path(cast("str", args.archive)).expanduser()
    partial = cast("bool", args.partial)
    date_text = cast("str | None", args.date)
    report = run / "report.html"
    html = report.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")
    errors: list[str] = []
    if locked_blocks(html) != locked_blocks(template):
        errors.append("<style> or <script> differs from the template; fill slots only and leave the design unchanged")
    if slots(html) != slots(template):
        errors.append("slot markers were removed, renamed or reordered; keep every <!-- slot:name --> pair")
    if "data-sample" in html:
        errors.append("sample content remains (data-sample); replace it in every slot, using an .empty line where a section has no rows")
    if EXTERNAL_RE.search(html):
        errors.append("external resource reference found; the report must be self-contained (plain <a href> links are fine)")
    if errors:
        fail("report not published:\n  " + "\n  ".join(errors))

    def inline(match: re.Match[str]) -> str:
        name = match.group(2)
        path = run / "fonts" / name
        if not path.is_file():
            path = ASSETS / "fonts" / name
        if not path.is_file():
            fail(f"font {name} not found")
        return f'url("data:font/woff2;base64,{base64.b64encode(path.read_bytes()).decode()}")'

    output = FONT_URL_RE.sub(inline, html)
    date = dt.date.fromisoformat(date_text) if date_text else dt.date.today()
    folder = archive / f"{date:%Y}"
    folder.mkdir(parents=True, exist_ok=True)
    suffix = "_PARTIAL" if partial else ""
    marker = run / ".published"
    previous = Path(marker.read_text(encoding="utf-8").strip()) if marker.is_file() else None
    target = folder / f"{date:%Y-%m-%d}_let-vps-report{suffix}.html"
    if target.exists() and target != previous:
        target = folder / f"{date:%Y-%m-%d}_{dt.datetime.now():%H%M}_let-vps-report{suffix}.html"
        n = 2
        while target.exists() and target != previous:
            target = folder / f"{date:%Y-%m-%d}_{dt.datetime.now():%H%M}-{n}_let-vps-report{suffix}.html"
            n += 1
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".let-vps-", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        _ = handle.write(output)
    umask = os.umask(0)
    _ = os.umask(umask)
    os.chmod(tmp, 0o666 & ~umask)
    os.replace(tmp, target)
    # One archived document per run: a later publish replaces this run's earlier file.
    if previous and previous != target and previous.is_file():
        previous.unlink()
        print(f"replaced {previous}")
    _ = marker.write_text(str(target), encoding="utf-8")
    print(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a run folder and print its path")
    _ = p.add_argument("--base", default=str(DEFAULT_BASE), help=f"parent folder (default {DEFAULT_BASE})")
    _ = p.add_argument("--archive", default=str(DEFAULT_ARCHIVE), help="archive folder recorded in STATUS.md")
    _ = p.add_argument("--browser", required=True, choices=BROWSERS, help="browser backend the user chose for this run")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("merge", help="merge worker files into the ledger")
    _ = p.add_argument("run")
    _ = p.add_argument("files", nargs="+")
    _ = p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("upsert", help="set fields on one row: upsert RUN TABLE KEY col=value ...")
    _ = p.add_argument("run")
    _ = p.add_argument("table")
    _ = p.add_argument("key")
    _ = p.add_argument("fields", nargs="*")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("summary", help="print counters and the verified ranking")
    _ = p.add_argument("run")
    _ = p.add_argument("--top", type=int, default=10)
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("publish", help="validate report.html and copy it to <archive>/<year>/")
    _ = p.add_argument("run")
    _ = p.add_argument("--archive", default=str(DEFAULT_ARCHIVE), help=f"archive folder (default {DEFAULT_ARCHIVE})")
    _ = p.add_argument("--partial", action="store_true", help="mark the report as partial coverage")
    _ = p.add_argument("--date", help="report date YYYY-MM-DD (default today)")
    p.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    func = cast("Callable[[argparse.Namespace], None]", args.func)  # every subparser sets func
    func(args)


if __name__ == "__main__":
    main()
