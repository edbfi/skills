#!/usr/bin/env python3
"""Check, hash and index guideline packs (references/pack-format.md). Read-only except `index`.

Usage:
  packs.py check [--reuse-from <library-root>] <pack-dir> ...
                                                 structure, pack.json, coverage, links, bytes
  packs.py check --library <library-root>        every pack under components/ and stacks/
  packs.py sources <pack-dir> [<pack-dir> ...]   citations resolve; claims cite sources
  packs.py hash <pack-dir>                       examples hash to record in pack.json
  packs.py index <library-root> [options]        write or --check INDEX.md; --stale; see --help

`--reuse-from` lets a draft stack resolve component packs and links that live in the existing
library because they were reused rather than rebuilt. `check` validates a pack by the rules of the
schema its pack.json declares, so a later builder adds a schema instead of retroactively failing
packs written under an earlier one. `sources` checks that
every `[S<n>]` citation outside code resolves to a row of sources.md, that every recommendation (a
'### ' section in practices/ or integration/), change item and anti-pattern cites at least one
source, and that no recommendation rests on community sources alone; unused sources are warnings.
Code blocks are checked by verify_examples.py. Exit status: 0 clean, 1 problems, 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

USAGE = (__doc__ or "").split("\n\n", 2)[1]


# ==================== Markdown, pack.json and checklist reading ====================
BUILDER_DIR = Path(__file__).resolve().parents[1]
CHECKLISTS = BUILDER_DIR / "references" / "checklists"
PACK_SCHEMAS = frozenset({1})

# Build and dependency output never belongs to an example's identity. Tool caches and dependency
# directories are skipped anywhere; names that are also ordinary source directory names (a
# `src/build/` package, `internal/dist/`) are skipped only at the example project's root.
ANYWHERE_IGNORED = frozenset({
    ".git", ".gradle", ".mypy_cache", ".next", ".pytest_cache", ".ruff_cache", ".svelte-kit",
    ".turbo", ".venv", "__pycache__", "node_modules",
})
PROJECT_ROOT_IGNORED = frozenset({".build", "DerivedData", "build", "dist", "target"})
IGNORED_FILES = frozenset({".DS_Store", "Thumbs.db"})

FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
HEADING = re.compile(r"^(?P<marks>#{1,6})[ \t]+(?P<title>.*?)[ \t]*$")
CITATION = re.compile(r"\[(S\d+)\]")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\((?P<target><[^>\n]+>|[^)\s]+)(?:[ \t]+\"[^\"\n]*\")?\)")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SOURCE_ID = re.compile(r"S\d+")
PUBLISHERS = frozenset({
    "official-docs", "release-notes", "changelog", "migration-guide", "spec", "source",
    "registry", "maintainer", "community",
})


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    index: int  # zero-based line index


@dataclass(frozen=True)
class Document:
    path: Path
    lines: list[str]
    in_code: list[bool]  # True for fence lines and lines inside fenced code
    headings: list[Heading]
    unclosed_fence: bool

    def section_end(self, heading: Heading) -> int:
        """Line index after the last line belonging to `heading` (sub-headings included)."""
        for other in self.headings:
            if other.index > heading.index and other.level <= heading.level:
                return other.index
        return len(self.lines)

    def direct_end(self, heading: Heading) -> int:
        """Line index of the next heading of any level, or the end of the document."""
        for other in self.headings:
            if other.index > heading.index:
                return other.index
        return len(self.lines)

    def text(self, start: int, end: int) -> str:
        return "\n".join(self.lines[start:end])

    def children(self, heading: Heading) -> list[Heading]:
        end = self.section_end(heading)
        return [h for h in self.headings if heading.index < h.index < end and h.level == heading.level + 1]

    def prose(self, start: int = 0, end: int | None = None) -> list[tuple[int, str]]:
        """(index, line) pairs outside code fences."""
        stop = len(self.lines) if end is None else end
        return [(i, self.lines[i]) for i in range(start, stop) if not self.in_code[i]]


def read_document(path: Path) -> Document:
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        del lines[-1]
    in_code: list[bool] = []
    headings: list[Heading] = []
    fence: str | None = None
    for index, line in enumerate(lines):
        match = FENCE.match(line)
        if fence is None:
            if match and not (match["fence"][0] == "`" and "`" in match["info"]):
                fence = match["fence"]
                in_code.append(True)
                continue
            in_code.append(False)
            heading = HEADING.match(line)
            if heading:
                headings.append(Heading(len(heading["marks"]), heading["title"], index))
        else:
            in_code.append(True)
            if match and match["fence"][0] == fence[0] and len(match["fence"]) >= len(fence) and not match["info"].strip():
                fence = None
    return Document(path, lines, in_code, headings, fence is not None)


def empty_sections(doc: Document) -> list[Heading]:
    """Headings with nothing but blank lines before the next heading of the same or higher level."""
    empty: list[Heading] = []
    for heading in doc.headings:
        end = doc.section_end(heading)
        body = [line for i, line in enumerate(doc.lines[heading.index + 1:end], heading.index + 1)
                if line.strip() and not (not doc.in_code[i] and HEADING.match(line))]
        if not body:
            empty.append(heading)
    return empty


def links(doc: Document) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for index, line in doc.prose():
        for match in LINK.finditer(line):
            target = match["target"].strip("<>")
            found.append((index, target))
    return found


def is_external(target: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)) or target.startswith("//")


def hygiene_problems(path: Path) -> list[str]:
    """Problems a whitespace fixer would rewrite, for files that decode as UTF-8 text."""
    data = path.read_bytes()
    if b"\0" in data:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    problems: list[str] = []
    if text.startswith("\ufeff"):
        problems.append("starts with a byte order mark")
    if "\r" in text:
        problems.append("contains CR line endings")
    if text and not text.endswith("\n"):
        problems.append("does not end with a newline")
    if text.endswith("\n\n"):
        problems.append("ends with blank lines")
    for number, line in enumerate(text.split("\n"), 1):
        if line != line.rstrip(" \t"):
            problems.append(f"line {number} has trailing whitespace")
            break
    return problems


def walk(root: Path, project: tuple[str, ...] = ()) -> list[Path]:
    """Files under `root`, skipping build and dependency output.

    `project` is the example project's root relative to `root`: `()` when walking an examples
    directory itself, `("examples",)` when walking a whole pack.
    """
    files: list[Path] = []
    depth = len(project)
    for path in sorted(root.rglob("*")):
        dirs = path.relative_to(root).parts[:-1]
        if any(part in ANYWHERE_IGNORED for part in dirs):
            continue
        if dirs[:depth] == project and len(dirs) > depth and dirs[depth] in PROJECT_ROOT_IGNORED:
            continue
        if path.is_file() and path.name not in IGNORED_FILES:
            files.append(path)
    return files


def tree_hash(root: Path) -> str:
    """sha256 over sorted `relative-path NUL sha256(file)` lines; ignored directories excluded."""
    digest = hashlib.sha256()
    for path in walk(root):
        rel = path.relative_to(root).as_posix()
        digest.update(f"{rel}\0{hashlib.sha256(path.read_bytes()).hexdigest()}\n".encode())
    return "sha256:" + digest.hexdigest()


# --- JSON helpers: json.loads returns Any, so values are narrowed explicitly. ---

def load_json(path: Path) -> object:
    return cast("object", json.loads(path.read_text(encoding="utf-8")))


def as_dict(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None  # JSON keys are strings


def as_list(value: object) -> list[object] | None:
    return cast("list[object]", value) if isinstance(value, list) else None


def as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def parse_date(value: object) -> date | None:
    text = as_str(value)
    if text is None or not ISO_DATE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# --- Sources table ---

SOURCE_COLUMNS = ("id", "title", "url", "publisher", "version", "checked")


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    url: str
    publisher: str
    version: str
    checked: str
    line: int


def table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped[1:-1])]


def parse_sources(doc: Document) -> tuple[list[Source], list[str]]:
    sources: list[Source] = []
    errors: list[str] = []
    header_seen = False
    for index, line in doc.prose():
        cells = table_cells(line)
        if cells is None:
            continue
        if not header_seen:
            if tuple(c.lower() for c in cells) != SOURCE_COLUMNS:
                errors.append(f"line {index + 1}: sources table header must be | {' | '.join(SOURCE_COLUMNS)} |")
                return sources, errors
            header_seen = True
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        if len(cells) != len(SOURCE_COLUMNS):
            errors.append(f"line {index + 1}: expected {len(SOURCE_COLUMNS)} cells, got {len(cells)}")
            continue
        sources.append(Source(*cells, line=index + 1))
    if not header_seen:
        errors.append("no sources table found")
    return sources, errors


# --- Checklists ---

@dataclass(frozen=True)
class Topic:
    id: str
    questions: list[str]


def checklist(kind: str, directory: Path = CHECKLISTS) -> list[Topic] | None:
    """Topics of `references/checklists/<kind>.md`, or None when the kind has no checklist."""
    path = directory / f"{kind}.md"
    if not re.fullmatch(r"[a-z0-9-]+", kind) or not path.is_file():
        return None
    doc = read_document(path)
    topics: list[Topic] = []
    for heading in doc.headings:
        if heading.level != 2:
            continue
        questions = [line[2:].strip() for _, line in doc.prose(heading.index + 1, doc.direct_end(heading))
                     if line.startswith("- ")]
        topics.append(Topic(heading.title.strip("`"), questions))
    return topics


def kinds(directory: Path = CHECKLISTS) -> list[str]:
    return sorted(path.stem for path in directory.glob("*.md"))


# ==================== check ====================
PACK_ID = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
TOPIC_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
APPLIES = re.compile(r"^Applies to \S.*\. Verified (?P<date>\d{4}-\d{2}-\d{2})\.$")
TITLE = re.compile(r"^.+ coding guidelines$")
CHANGE_ITEM = re.compile(r"^- \*\*(Breaking|New|Deprecated|Removed):\*\* \S")
AP_HEADING = re.compile(r"^AP-(?P<n>\d+): \S")
AP_FIELD = re.compile(r"^\*\*(?P<field>Category|Don't|Why|Do instead|Detect|Source):\*\*(?P<rest>.*)$")
AP_REQUIRED = ("Category", "Don't", "Why", "Do instead", "Source")
AP_CATEGORIES = frozenset({"Outdated", "Incorrect", "Risky"})
CONSTRAINT_SOURCES = frozenset({"user", "compat", "none"})
VERIFICATION_STATUSES = frozenset({"passed", "partial", "failed", "not-run"})
COMPONENT_README = ("How to use this pack", "Golden rules", "Most important recent changes", "Where to look")
STACK_README = ("How to use this pack", "Components", "Golden rules", "Where to look")
COMPONENT_FIELDS = ("Component", "Request", "Resolved", "Language mode", "Targets", "Researched",
                    "Refresh after", "Builder")
STACK_FIELDS = ("Stack", "Request", "Targets", "Researched", "Refresh after", "Builder")
LINE_CAPS = {"README.md": 200, "changes.md": 600, "anti-patterns.md": 600}
DEFAULT_CAP = 400
UNCAPPED = frozenset({"sources.md"})


class Checker:
    def __init__(self, pack: Path, reuse_from: tuple[Path, ...] = ()) -> None:
        self.pack: Path = pack
        # Libraries that hold component packs reused instead of rebuilt in this run's draft.
        self.reuse_from: tuple[Path, ...] = reuse_from
        self.errors: list[str] = []
        self.docs: dict[str, Document] = {}

    def library_path(self, path: Path) -> Path | None:
        """`path` inside this pack's library, or the same relative path in a reuse library."""
        library = self.pack.parent.parent.resolve()
        if not path.is_relative_to(library):
            return None
        if path.exists():
            return path
        rel = path.relative_to(library)
        return next((root / rel for root in self.reuse_from if (root / rel).exists()), None)

    def fail(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def rel(self, path: Path) -> str:
        return f"{self.pack.name}/{path.relative_to(self.pack).as_posix()}"

    def doc(self, name: str) -> Document | None:
        path = self.pack / name
        if name in self.docs:
            return self.docs[name]
        if not path.is_file():
            self.fail(f"{self.pack.name}/{name}", "missing")
            return None
        document = read_document(path)
        self.docs[name] = document
        return document

    # --- pack.json ---

    def field(self, data: dict[str, object], key: str, kind: type, nullable: bool = False) -> object:
        value = data.get(key)
        if value is None and nullable and key in data:
            return None
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            self.fail(f"{self.pack.name}/pack.json", f"{key!r} must be {'null or ' if nullable else ''}{kind.__name__}")
            return None
        return value

    def check_meta(self, data: dict[str, object]) -> None:
        where = f"{self.pack.name}/pack.json"
        pack_id = as_str(self.field(data, "id", str))
        if pack_id is not None and (not PACK_ID.fullmatch(pack_id) or pack_id != self.pack.name):
            self.fail(where, f"id {pack_id!r} must be lowercase [a-z0-9_-] and equal the directory name")
        for key in ("name", "request", "summary", "load_when"):
            value = as_str(self.field(data, key, str))
            if value is not None and not value.strip():
                self.fail(where, f"{key!r} must not be empty")
        researched = parse_date(data.get("researched"))
        refresh = parse_date(data.get("refresh_after"))
        if researched is None or refresh is None:
            self.fail(where, "'researched' and 'refresh_after' must be YYYY-MM-DD dates")
        elif refresh < researched:
            self.fail(where, "'refresh_after' is before 'researched'")
        _ = self.field(data, "targets", dict)
        builder = as_dict(self.field(data, "builder", dict))
        if builder is not None and not (as_str(builder.get("name")) and as_str(builder.get("version"))):
            self.fail(where, "'builder' needs string 'name' and 'version'")
        self.check_verification(as_dict(self.field(data, "verification", dict)))
        review = as_dict(self.field(data, "review", dict))
        if review is not None:
            if not isinstance(review.get("independent"), bool):
                self.fail(where, "'review.independent' must be a boolean")
            if parse_date(review.get("date")) is None:
                self.fail(where, "'review.date' must be a YYYY-MM-DD date")
            if as_list(review.get("open_items")) is None:
                self.fail(where, "'review.open_items' must be a list")

    def check_verification(self, verification: dict[str, object] | None) -> None:
        if verification is None:
            return
        where = f"{self.pack.name}/pack.json"
        if parse_date(verification.get("date")) is None:
            self.fail(where, "'verification.date' must be a YYYY-MM-DD date")
        if as_dict(verification.get("toolchain")) is None:
            self.fail(where, "'verification.toolchain' must be an object")
        commands = as_list(verification.get("commands"))
        if commands is None or not all(isinstance(c, str) and c.strip() for c in commands):
            self.fail(where, "'verification.commands' must be a list of commands")
        status = verification.get("status")
        if status not in VERIFICATION_STATUSES:
            self.fail(where, f"'verification.status' must be one of {sorted(VERIFICATION_STATUSES)}")
        limitations = as_list(verification.get("limitations"))
        if limitations is None or not all(isinstance(item, str) for item in limitations):
            self.fail(where, "'verification.limitations' must be a list of strings")
        elif status != "passed" and not limitations:
            self.fail(where, "a verification status other than 'passed' needs its limitations listed")
        blocks = as_dict(verification.get("blocks"))
        if blocks is None or any(not isinstance(blocks.get(k), int) for k in ("verified", "exempt_positional", "exempt_explicit")):
            self.fail(where, "'verification.blocks' needs integer verified, exempt_positional and exempt_explicit")
        recorded = as_str(verification.get("examples_hash"))
        examples = self.pack / "examples"
        if not examples.is_dir():
            self.fail(f"{self.pack.name}/examples", "missing")
        elif recorded != tree_hash(examples):
            self.fail(where, "'verification.examples_hash' does not match examples/; rerun verification and record the new hash")

    # --- Markdown shared rules ---

    def check_markdown(self, name: str, doc: Document) -> None:
        where = f"{self.pack.name}/{name}"
        if doc.unclosed_fence:
            self.fail(where, "unclosed code fence")
        titles = [h for h in doc.headings if h.level == 1]
        if len(titles) != 1 or (doc.headings and doc.headings[0].level != 1):
            self.fail(where, "needs exactly one '# ' title, before any other heading")
        for heading in empty_sections(doc):
            self.fail(where, f"line {heading.index + 1}: empty section {heading.title!r}")
        cap = LINE_CAPS.get(name, DEFAULT_CAP)
        if name not in UNCAPPED and len(doc.lines) > cap:
            self.fail(where, f"{len(doc.lines)} lines exceeds the {cap}-line cap; split it by topic")
        examples = (self.pack / "examples").resolve()
        for index, target in links(doc):
            if is_external(target) or target.startswith("#"):
                continue
            path_part = target.split("#", 1)[0]
            resolved = (doc.path.parent / path_part).resolve()
            if resolved.is_relative_to(examples):
                self.fail(where, f"line {index + 1}: link into examples/ ({target}); examples are not delivered")
            elif self.library_path(resolved) is None:
                self.fail(where, f"line {index + 1}: broken link {target}")

    def link_targets(self, doc: Document, start: int, end: int) -> set[Path]:
        targets: set[Path] = set()
        for index, target in links(doc):
            if start <= index < end and not is_external(target):
                targets.add((doc.path.parent / target.split("#", 1)[0]).resolve())
        return targets

    def h2(self, doc: Document, title: str) -> Heading | None:
        return next((h for h in doc.headings if h.level == 2 and h.title == title), None)

    def header_table(self, doc: Document, fields: tuple[str, ...]) -> dict[str, str]:
        first = next((h.index for h in doc.headings if h.level == 2), len(doc.lines))
        rows: dict[str, str] = {}
        for _, line in doc.prose(0, first):
            cells = table_cells(line)
            if cells and len(cells) >= 2:
                rows[cells[0]] = cells[1]
        missing = [f for f in fields if f not in rows]
        if missing:
            self.fail(f"{self.pack.name}/README.md", f"header table is missing {', '.join(missing)}")
        return rows

    def golden_rules(self, doc: Document) -> None:
        where = f"{self.pack.name}/README.md"
        section = self.h2(doc, "Golden rules")
        if section is None:
            return
        for title in ("MUST", "MUST NOT"):
            sub = next((h for h in doc.children(section) if h.title == title), None)
            if sub is None:
                self.fail(where, f"'Golden rules' needs a '### {title}' list")
                continue
            items = [(i, line) for i, line in doc.prose(sub.index + 1, doc.section_end(sub)) if line.startswith("- ")]
            if not 1 <= len(items) <= 15:
                self.fail(where, f"'{title}' needs 1 to 15 rules, found {len(items)}")
            for index, line in items:
                if not any(not is_external(m["target"]) for m in LINK.finditer(line)):
                    self.fail(where, f"line {index + 1}: golden rule must link to the file that explains it")

    def require_links(self, doc: Document, title: str, expected: list[Path]) -> None:
        section = self.h2(doc, title)
        if section is None:
            return
        found = self.link_targets(doc, section.index, doc.section_end(section))
        for path in expected:
            if path.resolve() not in found:
                self.fail(f"{self.pack.name}/README.md", f"'{title}' does not route to {path.relative_to(self.pack.parent.parent).as_posix()}")

    # --- topic and seam files ---

    def check_guidance_file(self, name: str, doc: Document, require_applies: bool = True) -> None:
        where = f"{self.pack.name}/{name}"
        first_h2 = next((h.index for h in doc.headings if h.level == 2), len(doc.lines))
        applies = [APPLIES.match(line) for _, line in doc.prose(0, first_h2)]
        if require_applies and not any(applies):
            self.fail(where, "needs an 'Applies to <version>. Verified <YYYY-MM-DD>.' line before the first section")
        sections = [h for h in doc.headings if h.level == 2]
        if not sections:
            self.fail(where, "needs at least one '## ' section")
        for heading in sections:
            if heading.title == "Pitfalls":
                continue
            if not any(h.level == 3 for h in doc.children(heading)):
                self.fail(where, f"line {heading.index + 1}: section {heading.title!r} needs at least one '### ' recommendation")

    def check_topics(self, data: dict[str, object]) -> None:
        where = f"{self.pack.name}/pack.json"
        kind = as_str(data.get("kind"))
        topics = as_dict(data.get("topics"))
        extra = as_dict(data.get("extra_topics"))
        if kind is None or topics is None or extra is None:
            self.fail(where, "'kind' must be a string and 'topics' and 'extra_topics' objects")
            return
        required = checklist(kind)
        if required is None:
            self.fail(where, f"no checklist for kind {kind!r}; available: {', '.join(kinds())}")
            return
        by_id = {t.id: t for t in required}
        for topic in required:
            if topic.id not in topics:
                self.fail(where, f"topic {topic.id!r} from the {kind} checklist is neither covered nor marked na")
        for key in topics:
            if key not in by_id:
                self.fail(where, f"topic {key!r} is not in the {kind} checklist; list it under 'extra_topics'")
        for key in extra:
            if not TOPIC_ID.fullmatch(key) or key in by_id:
                self.fail(where, f"extra topic {key!r} must be a lowercase id not already in the checklist")
        referenced: set[str] = set()
        for key, value in [*topics.items(), *extra.items()]:
            entry = as_dict(value)
            if entry is None:
                self.fail(where, f"topic {key!r} must be an object")
                continue
            if "na" in entry:
                if not as_str(entry.get("na")) or not SOURCE_ID.fullmatch(as_str(entry.get("source")) or ""):
                    self.fail(where, f"topic {key!r}: 'na' needs a reason and a 'source' id")
                if key in extra:
                    self.fail(where, f"extra topic {key!r} cannot be na; remove it instead")
                continue
            files = self.topic_files(key, entry)
            referenced.update(files)
            skipped: set[str] = set()
            for item in as_list(entry.get("na_sections")) or []:
                section = as_dict(item) or {}
                title = as_str(section.get("section"))
                if not title or not as_str(section.get("reason")) or not SOURCE_ID.fullmatch(as_str(section.get("source")) or ""):
                    self.fail(where, f"topic {key!r}: each na_sections entry needs 'section', 'reason' and 'source'")
                elif title:
                    skipped.add(title)
            present: set[str] = set()
            for name in files:
                doc = self.doc(name)
                if doc is not None:
                    present.update(h.title for h in doc.headings if h.level == 2)
            for question in by_id[key].questions if key in by_id else []:
                if question not in present and question not in skipped:
                    self.fail(where, f"topic {key!r}: no '## {question}' section and no na_sections entry for it")
        practices = self.pack / "practices"
        on_disk: set[str] = {f"practices/{p.name}" for p in practices.glob("*.md")} if practices.is_dir() else set()
        if not practices.is_dir():
            self.fail(f"{self.pack.name}/practices", "missing")
        for name in sorted(on_disk - referenced):
            self.fail(f"{self.pack.name}/{name}", "not referenced by any topic in pack.json")

    def topic_files(self, key: str, entry: dict[str, object]) -> list[str]:
        files = as_list(entry.get("files"))
        single = as_str(entry.get("file"))
        names = [single] if single is not None else [as_str(f) or "" for f in files or []]
        if not names or any(not re.fullmatch(rf"practices/{re.escape(key)}(?:-[a-z0-9-]+)?\.md", n) for n in names):
            self.fail(f"{self.pack.name}/pack.json", f"topic {key!r} needs 'file' or 'files' named practices/{key}[-<part>].md")
            return [n for n in names if n.startswith("practices/") and n.endswith(".md")]
        return names

    # --- fixed files ---

    def check_changes(self, doc: Document) -> None:
        where = f"{self.pack.name}/changes.md"
        releases = [h for h in doc.headings if h.level == 2]
        if not releases:
            self.fail(where, "needs one '## <release>' section per covered release")
        for heading in releases:
            items = [(i, l) for i, l in doc.prose(heading.index + 1, doc.section_end(heading)) if l.startswith("- ")]
            if not items:
                self.fail(where, f"release {heading.title!r} lists no changes")
            for index, line in items:
                if not CHANGE_ITEM.match(line):
                    self.fail(where, f"line {index + 1}: change items start with **Breaking:**, **New:**, **Deprecated:** or **Removed:**")

    def check_anti_patterns(self, doc: Document) -> None:
        where = f"{self.pack.name}/anti-patterns.md"
        entries = [h for h in doc.headings if h.level == 2]
        if not entries:
            self.fail(where, "needs at least one '## AP-<n>: <title>' entry")
        seen: set[str] = set()
        for heading in entries:
            match = AP_HEADING.match(heading.title)
            if not match:
                self.fail(where, f"line {heading.index + 1}: entries are titled 'AP-<n>: <title>'")
                continue
            if match["n"] in seen:
                self.fail(where, f"line {heading.index + 1}: duplicate AP-{match['n']}")
            seen.add(match["n"])
            fields: dict[str, str] = {}
            for _, line in doc.prose(heading.index + 1, doc.section_end(heading)):
                field = AP_FIELD.match(line)
                if field:
                    fields[field["field"]] = field["rest"].strip()
            missing = [f for f in AP_REQUIRED if f not in fields]
            if missing:
                self.fail(where, f"AP-{match['n']} is missing {', '.join('**' + m + ':**' for m in missing)}")
            if "Category" in fields and fields["Category"] not in AP_CATEGORIES:
                self.fail(where, f"AP-{match['n']}: Category must be one of {', '.join(sorted(AP_CATEGORIES))}")

    def check_sources_table(self, doc: Document) -> None:
        where = f"{self.pack.name}/sources.md"
        sources, problems = parse_sources(doc)
        for problem in problems:
            self.fail(where, problem)
        seen: set[str] = set()
        for source in sources:
            at = f"{where}: line {source.line}"
            if not SOURCE_ID.fullmatch(source.id) or source.id in seen:
                self.errors.append(f"{at}: id {source.id!r} must be a unique S<n>")
            seen.add(source.id)
            if not re.match(r"^https?://\S+$", source.url):
                self.errors.append(f"{at}: url must be http(s)")
            if source.publisher not in PUBLISHERS:
                self.errors.append(f"{at}: publisher must be one of {', '.join(sorted(PUBLISHERS))}")
            if not source.title or not source.version:
                self.errors.append(f"{at}: title and version must not be empty")
            if parse_date(source.checked) is None:
                self.errors.append(f"{at}: checked must be a YYYY-MM-DD date")
        if not sources and not problems:
            self.fail(where, "lists no sources")

    def check_files(self) -> None:
        for path in walk(self.pack, ("examples",)):
            if path.name.lower() == "skill.md":
                self.fail(self.rel(path), "a guidelines pack must not contain a SKILL.md")
            for problem in hygiene_problems(path):
                self.fail(self.rel(path), problem)

    # --- pack types ---

    def run(self) -> list[str]:
        meta_path = self.pack / "pack.json"
        if not meta_path.is_file():
            self.fail(f"{self.pack.name}/pack.json", "missing")
            return self.errors
        try:
            data = as_dict(load_json(meta_path))
        except (ValueError, UnicodeDecodeError) as error:
            self.fail(f"{self.pack.name}/pack.json", f"unreadable: {error}")
            return self.errors
        if data is None:
            self.fail(f"{self.pack.name}/pack.json", "must be a JSON object")
            return self.errors
        schema = data.get("schema")
        if not isinstance(schema, int) or isinstance(schema, bool) or schema not in PACK_SCHEMAS:
            self.fail(f"{self.pack.name}/pack.json", f"schema {schema!r} is not supported by this builder (supports {sorted(PACK_SCHEMAS)})")
            return self.errors
        pack_type = data.get("type")
        expected_parent = {"component": "components", "stack": "stacks"}.get(str(pack_type))
        if expected_parent is None:
            self.fail(f"{self.pack.name}/pack.json", "'type' must be 'component' or 'stack'")
            return self.errors
        if self.pack.parent.name != expected_parent:
            self.fail(self.pack.name, f"a {pack_type} pack lives in <library>/{expected_parent}/")
        self.check_meta(data)
        self.check_files()
        if pack_type == "component":
            self.check_component(data)
        else:
            self.check_stack(data)
        examples = self.pack / "examples"
        for path in walk(self.pack, ("examples",)):
            if path.suffix == ".md" and not path.is_relative_to(examples):
                _ = self.doc(path.relative_to(self.pack).as_posix())
        for name in sorted(self.docs):
            self.check_markdown(name, self.docs[name])
        return self.errors

    def common_docs(self, with_changes: bool) -> None:
        changes = self.doc("changes.md") if with_changes else None
        if changes is not None:
            self.check_changes(changes)
        anti = self.doc("anti-patterns.md")
        if anti is not None:
            self.check_anti_patterns(anti)
        sources = self.doc("sources.md")
        if sources is not None:
            self.check_sources_table(sources)

    def check_component(self, data: dict[str, object]) -> None:
        where = f"{self.pack.name}/pack.json"
        _ = self.field(data, "resolved", str)
        _ = self.field(data, "constraint", str, nullable=True)
        _ = self.field(data, "language_mode", str, nullable=True)
        _ = self.field(data, "registry", dict, nullable=True)
        if data.get("constraint_source") not in CONSTRAINT_SOURCES:
            self.fail(where, f"'constraint_source' must be one of {sorted(CONSTRAINT_SOURCES)}")
        narrowed = as_list(data.get("narrowed_by"))
        if narrowed is None:
            self.fail(where, "'narrowed_by' must be a list")
        elif data.get("constraint_source") == "compat" and not narrowed:
            self.fail(where, "a compat-derived constraint needs 'narrowed_by' entries")
        self.check_topics(data)
        for name in [n for n in self.docs if n.startswith("practices/")]:
            self.check_guidance_file(name, self.docs[name])
        readme = self.doc("README.md")
        if readme is not None:
            self.check_readme(readme, data, COMPONENT_README, COMPONENT_FIELDS)
            practices = sorted((self.pack / "practices").glob("*.md"))
            self.require_links(readme, "Where to look", [*practices, self.pack / "changes.md", self.pack / "anti-patterns.md"])
            self.require_links(readme, "Most important recent changes", [self.pack / "changes.md"])
            section = self.h2(readme, "Most important recent changes")
            if section is not None:
                items = [l for _, l in readme.prose(section.index + 1, readme.section_end(section)) if l.startswith("- ")]
                if not 1 <= len(items) <= 10:
                    self.fail(f"{self.pack.name}/README.md", f"'Most important recent changes' needs 1 to 10 items, found {len(items)}")
        self.common_docs(with_changes=True)

    def check_readme(self, doc: Document, data: dict[str, object], sections: tuple[str, ...], fields: tuple[str, ...]) -> None:
        where = f"{self.pack.name}/README.md"
        title = next((h for h in doc.headings if h.level == 1), None)
        if title is not None and not TITLE.match(title.title):
            self.fail(where, "title must read '# <Name> coding guidelines'")
        rows = self.header_table(doc, fields)
        for field, key in (("Resolved", "resolved"), ("Researched", "researched"), ("Refresh after", "refresh_after")):
            if field in rows and key in data and rows[field].strip("`") != data[key]:
                self.fail(where, f"header {field!r} is {rows[field]!r} but pack.json says {data[key]!r}")
        for section in sections:
            if self.h2(doc, section) is None:
                self.fail(where, f"missing '## {section}'")
        self.golden_rules(doc)

    def check_stack(self, data: dict[str, object]) -> None:
        where = f"{self.pack.name}/pack.json"
        _ = self.field(data, "request_normalized", dict)
        library = self.pack.parent.parent
        edges = as_list(data.get("components"))
        component_readmes: list[Path] = []
        if not edges:
            self.fail(where, "'components' must list the stack's component packs")
        for item in edges or []:
            edge = as_dict(item) or {}
            edge_id = as_str(edge.get("id"))
            if edge_id is None or not all(isinstance(edge.get(k), str) for k in ("original_request", "reason", "resolved")) \
                    or not (edge.get("effective_constraint") is None or isinstance(edge.get("effective_constraint"), str)):
                self.fail(where, "each component edge needs id, original_request, effective_constraint (string or null), reason and resolved")
                continue
            in_library = (library / "components" / edge_id).resolve()
            target = self.library_path(in_library / "pack.json")
            if target is None:
                self.fail(where, f"component pack {edge_id!r} does not exist in the library")
                continue
            component_readmes.append(in_library / "README.md")
            try:
                resolved = (as_dict(load_json(target)) or {}).get("resolved")
            except (ValueError, UnicodeDecodeError):
                resolved = None
            if resolved != edge.get("resolved"):
                self.fail(where, f"edge {edge_id!r} records {edge.get('resolved')!r} but the component pack resolves {resolved!r}; refresh this stack")
        integrations = as_dict(data.get("integrations"))
        seam_files: list[Path] = []
        if integrations is None:
            self.fail(where, "'integrations' must be an object")
        for key, value in (integrations or {}).items():
            entry = as_dict(value) or {}
            if "na" in entry:
                if not as_str(entry.get("na")) or not SOURCE_ID.fullmatch(as_str(entry.get("source")) or ""):
                    self.fail(where, f"seam {key!r}: 'na' needs a reason and a 'source' id")
                continue
            name = as_str(entry.get("file"))
            if name is None or name != f"integration/{key}.md":
                self.fail(where, f"seam {key!r} needs 'file': 'integration/{key}.md' or an 'na' reason")
                continue
            doc = self.doc(name)
            if doc is not None:
                seam_files.append(self.pack / name)
                self.check_guidance_file(name, doc)
        on_disk: set[Path] = set((self.pack / "integration").glob("*.md")) if (self.pack / "integration").is_dir() else set()
        for path in sorted(on_disk - set(seam_files)):
            self.fail(self.rel(path), "not listed under 'integrations' in pack.json")
        for name in ("versions.md", "decisions.md"):
            _ = self.doc(name)
        readme = self.doc("README.md")
        if readme is not None:
            self.check_readme(readme, data, STACK_README, STACK_FIELDS)
            self.require_links(readme, "Components", component_readmes)
            self.require_links(readme, "Where to look", [*seam_files, *(self.pack / n for n in ("versions.md", "decisions.md", "anti-patterns.md"))])
        self.common_docs(with_changes=False)


def library_packs(root: Path) -> list[Path]:
    return sorted(p.parent for kind in ("components", "stacks") for p in (root / kind).glob("*/pack.json"))


def check_main(args: list[str]) -> int:
    reuse_from: list[Path] = []
    while len(args) >= 2 and args[0] == "--reuse-from":
        if not Path(args[1]).is_dir():
            print(f"not a directory: {args[1]}", file=sys.stderr)
            return 2
        reuse_from.append(Path(args[1]).resolve())
        args = args[2:]
    if len(args) == 2 and args[0] == "--library":
        root = Path(args[1])
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return 2
        packs = library_packs(root)
    elif args and not any(a.startswith("--") for a in args):
        packs = [Path(a) for a in args]
    else:
        print(USAGE, file=sys.stderr)
        return 2
    errors: list[str] = []
    for pack in packs:
        if not pack.is_dir():
            print(f"not a directory: {pack}", file=sys.stderr)
            return 2
        errors.extend(Checker(pack.resolve(), tuple(reuse_from)).run())
    for error in errors:
        print(error)
    print(f"checked {len(packs)} pack(s): {len(errors)} problem(s)")
    return 1 if errors else 0


def hash_main(args: list[str]) -> int:
    if len(args) != 1 or args[0].startswith("--"):
        print(USAGE, file=sys.stderr)
        return 2
    examples = Path(args[0]) / "examples"
    if not examples.is_dir():
        print(f"no examples directory in {args[0]}", file=sys.stderr)
        return 2
    print(tree_hash(examples))
    return 0

# ==================== sources ====================
def cited(doc: Document, start: int, end: int) -> list[str]:
    return [m[1] for _, line in doc.prose(start, end) for m in CITATION.finditer(line)]


def pack_json_sources(data: dict[str, object]) -> list[tuple[str, str]]:
    """(where, source id) for every source pack.json relies on."""
    found: list[tuple[str, str]] = []
    for group in ("topics", "extra_topics", "integrations"):
        for key, value in (as_dict(data.get(group)) or {}).items():
            entry = as_dict(value) or {}
            if "na" in entry:
                found.append((f"{group}.{key}", as_str(entry.get("source")) or ""))
            for item in as_list(entry.get("na_sections")) or []:
                found.append((f"{group}.{key}.na_sections", as_str((as_dict(item) or {}).get("source")) or ""))
    for item in as_list(data.get("narrowed_by")) or []:
        found.append(("narrowed_by", as_str((as_dict(item) or {}).get("source")) or ""))
    return found


def check_sources(pack: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    name = pack.name
    sources_path = pack / "sources.md"
    if not sources_path.is_file():
        return [f"{name}/sources.md: missing"], warnings
    rows, problems = parse_sources(read_document(sources_path))
    errors.extend(f"{name}/sources.md: {p}" for p in problems)
    sources = {row.id: row for row in rows}
    used: set[str] = set()

    examples = pack / "examples"
    for path in walk(pack, ("examples",)):
        if path.suffix != ".md" or path.is_relative_to(examples) or path == sources_path:
            continue
        rel = path.relative_to(pack).as_posix()
        where = f"{name}/{rel}"
        doc = read_document(path)
        for index, line in doc.prose():
            for match in CITATION.finditer(line):
                used.add(match[1])
                if match[1] not in sources:
                    errors.append(f"{where}: line {index + 1}: [{match[1]}] is not in sources.md")
        if rel.startswith(("practices/", "integration/")):
            for heading in (h for h in doc.headings if h.level == 3):
                ids = cited(doc, heading.index + 1, doc.section_end(heading))
                if not ids:
                    errors.append(f"{where}: line {heading.index + 1}: recommendation {heading.title!r} cites no source")
                elif all(sources[i].publisher == "community" for i in ids if i in sources) and all(i in sources for i in ids):
                    errors.append(f"{where}: line {heading.index + 1}: recommendation {heading.title!r} rests on community sources only")
        elif rel == "changes.md":
            items: list[tuple[int, list[str]]] = []
            current: list[str] | None = None
            for index, line in doc.prose():
                if line.startswith("- "):
                    current = [m[1] for m in CITATION.finditer(line)]
                    items.append((index, current))
                elif current is not None and line.startswith("  ") and line.strip():
                    current.extend(m[1] for m in CITATION.finditer(line))
                else:
                    current = None
            for index, ids in items:
                if not ids:
                    errors.append(f"{where}: line {index + 1}: change item cites no source")
        elif rel == "anti-patterns.md":
            for heading in (h for h in doc.headings if h.level == 2):
                source_lines = [line for _, line in doc.prose(heading.index + 1, doc.section_end(heading))
                                if line.startswith("**Source:**")]
                if source_lines and not CITATION.search(source_lines[0]):
                    errors.append(f"{where}: line {heading.index + 1}: {heading.title.split(':')[0]} **Source:** cites no source id")

    meta = pack / "pack.json"
    if meta.is_file():
        try:
            data = as_dict(load_json(meta)) or {}
        except (ValueError, UnicodeDecodeError):
            data = {}
        for where, source_id in pack_json_sources(data):
            used.add(source_id)
            if source_id not in sources:
                errors.append(f"{name}/pack.json: {where} cites {source_id or 'nothing'}, which is not in sources.md")
    warnings.extend(f"{name}/sources.md: line {row.line}: {row.id} is never cited" for row in rows if row.id not in used)
    return errors, warnings


def sources_main(args: list[str]) -> int:
    packs = [Path(a) for a in args]
    if not packs or any(str(p).startswith("--") or not p.is_dir() for p in packs):
        print(USAGE, file=sys.stderr)
        return 2
    errors: list[str] = []
    warnings: list[str] = []
    for pack in packs:
        found, warned = check_sources(pack.resolve())
        errors.extend(found)
        warnings.extend(warned)
    for line in errors:
        print(line)
    for line in warnings:
        print(f"warning: {line}")
    print(f"checked {len(packs)} pack(s): {len(errors)} problem(s), {len(warnings)} warning(s)")
    return 1 if errors else 0

# ==================== index ====================
INDEX_HELP = """Write <library-root>/INDEX.md from every pack.json. The output is deterministic (no\ntimestamps), so --check fails when the committed index is out of date. --only limits the index to a\ndelivered subset, as in a consumer repository. --warn-unreferenced lists component packs that no\nstack uses and that --referenced (a manifest's direct entries) does not name. --stale lists packs\nwhose refresh_after date has passed and exits 1 when there are any; it does not write the index."""


@dataclass(frozen=True)
class IndexedPack:
    key: str  # "components/<id>" or "stacks/<id>"
    name: str
    kind: str
    resolved: str
    researched: str
    refresh_after: str
    components: tuple[str, ...]


def read_packs(root: Path) -> tuple[list[IndexedPack], list[str]]:
    packs: list[IndexedPack] = []
    errors: list[str] = []
    for group in ("components", "stacks"):
        for meta in sorted((root / group).glob("*/pack.json")):
            key = f"{group}/{meta.parent.name}"
            try:
                data = as_dict(load_json(meta))
            except (ValueError, UnicodeDecodeError) as error:
                errors.append(f"{key}/pack.json: unreadable: {error}")
                continue
            if data is None:
                errors.append(f"{key}/pack.json: must be a JSON object")
                continue
            edges = [as_str((as_dict(e) or {}).get("id")) for e in as_list(data.get("components")) or []]
            packs.append(IndexedPack(
                key=key,
                name=as_str(data.get("name")) or meta.parent.name,
                kind=as_str(data.get("kind")) or "stack",
                resolved=as_str(data.get("resolved")) or "",
                researched=as_str(data.get("researched")) or "",
                refresh_after=as_str(data.get("refresh_after")) or "",
                components=tuple(f"components/{e}" for e in edges if e),
            ))
    return packs, errors


def render(packs: list[IndexedPack]) -> str:
    used_by: dict[str, list[str]] = {}
    for pack in packs:
        for component in pack.components:
            used_by.setdefault(component, []).append(pack.key)

    def link(key: str) -> str:
        return f"[`{key.split('/', 1)[1]}`]({key}/README.md)"

    lines = ["# Guidelines index", "",
             "Generated by `packs.py index` from each pack's `pack.json`; do not edit by hand.",
             "Open a pack's `README.md` first; it routes to the topic files.", ""]
    stacks = [p for p in packs if p.key.startswith("stacks/")]
    components = [p for p in packs if p.key.startswith("components/")]
    if stacks:
        lines += ["## Stacks", "", "| Pack | Name | Components | Researched | Refresh after |", "|---|---|---|---|---|"]
        for p in stacks:
            names = ", ".join(c.split("/", 1)[1] for c in p.components)
            lines.append(f"| {link(p.key)} | {p.name} | {names} | {p.researched} | {p.refresh_after} |")
        lines.append("")
    if components:
        lines += ["## Components", "", "| Pack | Name | Kind | Version | Researched | Refresh after | Used by |",
                  "|---|---|---|---|---|---|---|"]
        for p in components:
            users = ", ".join(s.split("/", 1)[1] for s in used_by.get(p.key, [])) or "-"
            lines.append(f"| {link(p.key)} | {p.name} | {p.kind} | {p.resolved} | {p.researched} | {p.refresh_after} | {users} |")
        lines.append("")
    if not packs:
        lines += ["No packs yet.", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


class IndexArguments(argparse.Namespace):
    root: Path = Path()
    only: str | None = None
    referenced: str = ""
    check: bool = False
    stale: bool = False
    warn_unreferenced: bool = False
    today: str | None = None


def split_keys(value: str | None) -> list[str]:
    return [k.strip().strip("/") for k in (value or "").split(",") if k.strip()]


def index_main(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="packs.py index", description=INDEX_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("root", type=Path)
    _ = parser.add_argument("--only")
    _ = parser.add_argument("--referenced", default="")
    _ = parser.add_argument("--check", action="store_true")
    _ = parser.add_argument("--stale", action="store_true")
    _ = parser.add_argument("--warn-unreferenced", action="store_true")
    _ = parser.add_argument("--today")
    options = parser.parse_args(args, namespace=IndexArguments())
    if not options.root.is_dir():
        print(f"not a directory: {options.root}", file=sys.stderr)
        return 2
    packs, errors = read_packs(options.root)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 2
    only = split_keys(options.only)
    if options.only is not None:
        known = {p.key for p in packs}
        missing = [k for k in only if k not in known]
        if missing:
            print(f"unknown pack(s): {', '.join(missing)}", file=sys.stderr)
            return 2
        packs = [p for p in packs if p.key in only]

    if options.stale:
        today = parse_date(options.today) if options.today else date.today()
        if today is None:
            print("--today must be YYYY-MM-DD", file=sys.stderr)
            return 2
        stale = [p for p in packs if (due := parse_date(p.refresh_after)) is None or due < today]
        for pack in stale:
            print(f"stale: {pack.key} (refresh after {pack.refresh_after or 'unknown'})")
        print(f"{len(stale)} stale pack(s) of {len(packs)}")
        return 1 if stale else 0

    if options.warn_unreferenced:
        referenced = set(split_keys(options.referenced))
        used = {c for p in packs for c in p.components}
        for pack in packs:
            if pack.key.startswith("components/") and pack.key not in used and pack.key not in referenced:
                print(f"warning: {pack.key} is not used by any stack or listed entry", file=sys.stderr)

    index = options.root / "INDEX.md"
    content = render(packs)
    if options.check:
        current = index.read_text(encoding="utf-8") if index.is_file() else None
        if current != content:
            print(f"{index} is out of date; run packs.py index {options.root}")
            return 1
        print(f"{index} is current")
        return 0
    _ = index.write_text(content, encoding="utf-8")
    print(f"wrote {index} ({len(packs)} pack(s))")
    return 0


COMMANDS = {"check": check_main, "sources": sources_main, "hash": hash_main, "index": index_main}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
