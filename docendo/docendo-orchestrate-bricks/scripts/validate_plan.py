#!/usr/bin/env python3
"""Validate an occurrence plan; optional module policy is supplied separately."""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import cast

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YEAR_RE = re.compile(r"^(\d{4})[-/](\d{2}|\d{4})$")


def as_object(value: object) -> dict[str, object] | None:
    """A parsed JSON object, or None for any other value."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None  # JSON object keys are strings


def as_array(value: object) -> list[object] | None:
    """A parsed JSON array, or None for any other value."""
    return cast("list[object]", value) if isinstance(value, list) else None


def minutes(value: object) -> int:
    if not isinstance(value, str) or not TIME_RE.fullmatch(value):
        raise ValueError(f"invalid HH:MM time: {value!r}")
    h, m = map(int, value.split(":"))
    return h * 60 + m


def iso_date(value: object) -> date:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ValueError(f"invalid ISO date: {value!r}")
    return date.fromisoformat(value)


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def required_text(item: dict[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a nonempty string")
    return value


def validate(data: object, profile: object = None) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[str] = []
    plan = as_object(data)
    if plan is None:
        return ["plan must be an object"], warnings, rows
    match = YEAR_RE.fullmatch(str(plan.get("school_year", "")))
    years: tuple[int, int] | None = None
    if match:
        first, last = match.groups()
        last = first[:2] + last if len(last) == 2 else last
        years = (int(first), int(last))
    if not years or years[1] != years[0] + 1:
        errors.append("school_year must contain consecutive years, e.g. 2026-2027")
    if not nonempty(plan.get("calendar_id")):
        errors.append("calendar_id must be a nonempty string")
    period = as_object(plan.get("period", {}))
    lower: date | None = None
    upper: date | None = None
    try:
        if period is None:
            raise ValueError("must be an object")
        lower, upper = iso_date(period.get("start")), iso_date(period.get("end"))
        if lower > upper:
            raise ValueError("period start is after end")
        if years and (lower.year not in years or upper.year not in years):
            raise ValueError("period does not fit school_year")
    except ValueError as exc:
        errors.append(f"period: {exc}; use the actual Docendo period")
    modules: list[tuple[int, int]] = []
    if profile is not None:
        try:
            policy = as_object(profile)
            if policy is None:
                raise TypeError("profile must be an object")
            items = as_array(policy["modules"])
            if items is None:
                raise TypeError("modules must be an array")
            for item in items:
                module = as_object(item)
                if module is None:
                    raise TypeError("each module must be an object")
                start, end = minutes(module["start"]), minutes(module["end"])
                if start >= end:
                    raise ValueError("module end must follow start")
                modules.append((start, end))
            modules.sort()
            if not modules or any(a[1] > b[0] for a, b in zip(modules, modules[1:])):
                raise ValueError("modules must be nonempty and nonoverlapping")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"profile: {exc}")
    events = as_array(plan.get("events"))
    if events is None:
        return errors + ["events must be an array"], warnings, rows
    seen: set[tuple[str, str, int, int, bool]] = set()
    by_date: dict[date, list[tuple[int, int, str, int]]] = {}
    for index, item in enumerate(events, 1):
        label = f"event {index}"
        try:
            event = as_object(item)
            if event is None:
                raise ValueError("must be an object")
            title = required_text(event, "title")
            _ = required_text(event, "source")
            day = iso_date(required_text(event, "date"))
            if lower and upper and not lower <= day <= upper:
                raise ValueError("date is outside the actual Docendo period")
            all_day = event.get("all_day", False)
            if not isinstance(all_day, bool):
                raise ValueError("all_day must be a boolean")
            layout = event.get("layout")
            if layout not in (None, "module", "continuous"):
                raise ValueError("layout must be module or continuous")
            if profile is not None and layout is None:
                raise ValueError("layout is required with a module profile")
            if layout == "module" and not modules:
                raise ValueError("module layout requires a valid module profile")
            if all_day:
                if any(key in event for key in ("start", "end")):
                    raise ValueError("all-day events must omit start/end")
                if layout == "module":
                    raise ValueError("split a school day into timed module occurrences")
                start, end = 0, 1440
            else:
                start, end = minutes(event.get("start")), minutes(event.get("end"))
                if end <= start:
                    raise ValueError("end must follow start; overnight spans need an explicit workflow")
                if layout == "module" and not any(a <= start < end <= b for a, b in modules):
                    raise ValueError("not wholly inside one module; split at breaks preserving outer times")
            if layout == "continuous" and not nonempty(event.get("classification_source")):
                raise ValueError("continuous layout requires classification_source (source/user reason)")
            key = (title.strip(), day.isoformat(), start, end, all_day)
            if key in seen:
                raise ValueError("exact duplicate")
            seen.add(key)
            by_date.setdefault(day, []).append((start, end, title, index))
            time_text = "ALL-DAY" if all_day else f"{event['start']}-{event['end']}"
            rows.append(f"{day} {day.strftime('%A'):<9} W{day.isocalendar().week:02} {time_text} {title}")
        except (ValueError, TypeError) as exc:
            errors.append(f"{label}: {exc}")
    # Include enclosing overlaps and all-day events, not just adjacent pairs.
    for day, items in by_date.items():
        items.sort()
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                if b[0] >= a[1]:
                    break
                warnings.append(f"{day}: overlap between event {a[3]} ({a[2]}) and event {b[3]} ({b[2]})")
    return errors, warnings, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("plan", type=Path)
    _ = parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    # argparse converts both through type=Path; --profile stays None when omitted.
    plan_path, profile_path = cast("Path", args.plan), cast("Path | None", args.profile)
    try:
        data = cast("object", json.loads(plan_path.read_text()))
        profile = cast("object", json.loads(profile_path.read_text())) if profile_path else None
        errors, warnings, rows = validate(data, profile)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for row in rows:
        print(row)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {len(rows)} events validated; {len(warnings)} overlap warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
