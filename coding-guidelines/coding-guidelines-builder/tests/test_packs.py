"""Offline tests for packs.py: pack structure, citations, examples hash and the library index."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class TopicLike(Protocol):
    id: str
    questions: list[str]


def load_packs() -> ModuleType:
    spec = importlib.util.spec_from_file_location("packs", SCRIPTS / "packs.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["packs"] = module  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(module)
    return module


PACKS = load_packs()
# These signatures are defined by the local module loaded from the path above.
tree_hash = cast("Callable[[Path], str]", PACKS.tree_hash)
checklist = cast("Callable[[str], list[TopicLike] | None]", PACKS.checklist)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(content, encoding="utf-8")


def build_component(library: Path, pack_id: str = "zod-4", resolved: str = "4.1.0") -> Path:
    """A valid component pack of kind `library`, covering every checklist topic."""
    pack = library / "components" / pack_id
    topics = checklist("library")
    assert topics is not None
    write(pack / "examples/src/good.ts", "export const ok = 1;\n")
    for topic in topics:
        sections = "".join(
            f"## {q}\n\n### Prefer the documented form for {q.lower()}\n\nIt is the current recommendation. [S1]\n\n"
            for q in topic.questions)
        body = f"# {topic.id}: Zod 4\n\nApplies to {resolved}. Verified 2026-10-17.\n\n{sections}"
        write(pack / f"practices/{topic.id}.md", body.rstrip("\n") + "\n")
    where = "".join(f"| {t.id} | [{t.id}](practices/{t.id}.md) |\n" for t in topics)
    write(pack / "README.md", f"""# Zod 4 coding guidelines

| Field | Value |
|---|---|
| Component | Zod |
| Request | Zod 4 |
| Resolved | {resolved} |
| Language mode | n/a |
| Targets | none |
| Researched | 2026-10-17 |
| Refresh after | 2027-01-15 |
| Builder | coding-guidelines-builder 2.0.0 |

## How to use this pack

Read this file first, then the topic file for the task.

## Golden rules

### MUST

- Parse untrusted input at the boundary ([core](practices/core-api.md)).

### MUST NOT

- Trust unparsed data ([errors](practices/errors.md)).

## Most important recent changes

- Error customisation moved ([changes](changes.md)).

## Where to look

| Task | File |
|---|---|
{where}| Recent changes | [changes](changes.md) |
| Review | [anti-patterns](anti-patterns.md) |
""")
    write(pack / "changes.md", "# Zod changes\n\n## 4.0\n\n- **Breaking:** the error map API changed; use `error`. [S1]\n"
          + "  Continuation lines may cite too. [S2]\n")
    write(pack / "anti-patterns.md", """# Zod anti-patterns

## AP-1: Casting instead of parsing

**Category:** Incorrect
**Don't:** cast unparsed data.
```ts
const user = input as User;
```
**Why:** a cast checks nothing at runtime. [S1]
**Do instead:** parse it.
<!-- example: src/good.ts -->
```ts
export const ok = 1;
```
**Source:** [S1]
""")
    write(pack / "sources.md", """# Sources

| id | title | url | publisher | version | checked |
|---|---|---|---|---|---|
| S1 | Zod 4 docs | https://zod.dev/ | official-docs | 4.1 | 2026-10-17 |
| S2 | Zod changelog | https://github.com/colinhacks/zod/releases | changelog | 4.1 | 2026-10-17 |
""")
    meta: dict[str, object] = {
        "schema": 1, "id": pack_id, "type": "component", "kind": "library", "name": "Zod",
        "request": "Zod 4", "constraint": "4", "constraint_source": "user", "narrowed_by": [],
        "resolved": resolved, "language_mode": None, "targets": {},
        "registry": {"type": "npm", "package": "zod"}, "researched": "2026-10-17", "refresh_after": "2027-01-15",
        "summary": "Zod 4 validation.", "load_when": "Validating data with Zod",
        "topics": {t.id: {"file": f"practices/{t.id}.md"} for t in topics}, "extra_topics": {},
        "verification": {"date": "2026-10-17", "toolchain": {"bun": "1.4.3"}, "commands": ["bun test"],
                         "examples_hash": tree_hash(pack / "examples"),
                         "blocks": {"verified": 1, "exempt_positional": 1, "exempt_explicit": 0},
                         "status": "passed", "limitations": []},
        "review": {"independent": True, "date": "2026-10-17", "open_items": []},
        "builder": {"name": "coding-guidelines-builder", "version": "2.0.0"},
    }
    write(pack / "pack.json", json.dumps(meta, indent=2) + "\n")
    return pack


def build_stack(library: Path, component: str = "zod-4", resolved: str = "4.1.0") -> Path:
    pack = library / "stacks" / "bun-zod"
    write(pack / "examples/index.ts", "export {};\n")
    write(pack / "integration/zod-bun.md", "# Zod on Bun\n\nApplies to 4.1.0 on Bun 1.4.3. Verified 2026-10-17.\n\n"
          + "## Wiring\n\n### Parse request bodies before use\n\nBun hands over unknown JSON. [S1]\n")
    write(pack / "versions.md", "# Versions\n\n| Component | Version |\n|---|---|\n| Zod | 4.1.0 |\n")
    write(pack / "decisions.md", "# Decisions\n\nBun runs the tests.\n")
    write(pack / "anti-patterns.md", "# Stack anti-patterns\n\n## AP-1: Parsing twice\n\n**Category:** Risky\n"
          + "**Don't:** parse in every layer.\n**Why:** it hides the boundary. [S1]\n**Do instead:** parse once.\n**Source:** [S1]\n")
    write(pack / "sources.md", "# Sources\n\n| id | title | url | publisher | version | checked |\n|---|---|---|---|---|---|\n"
          + "| S1 | Bun docs | https://bun.sh/docs | official-docs | 1.4 | 2026-10-17 |\n")
    write(pack / "README.md", f"""# Bun and Zod coding guidelines

| Field | Value |
|---|---|
| Stack | Bun, Zod |
| Request | Bun, Zod 4 |
| Targets | none |
| Researched | 2026-10-17 |
| Refresh after | 2027-01-15 |
| Builder | coding-guidelines-builder 2.0.0 |

## How to use this pack

Read this file, then the component packs.

## Components

| Component | Version | Guidelines |
|---|---|---|
| Zod | {resolved} | [zod](../../components/{component}/README.md) |

## Golden rules

### MUST

- Parse at the edge ([seam](integration/zod-bun.md)).

### MUST NOT

- Parse twice ([anti-patterns](anti-patterns.md)).

## Where to look

- [Zod on Bun](integration/zod-bun.md), [versions](versions.md), [decisions](decisions.md), [anti-patterns](anti-patterns.md)
""")
    meta: dict[str, object] = {
        "schema": 1, "id": "bun-zod", "type": "stack", "name": "Bun and Zod", "request": "Bun, Zod 4",
        "request_normalized": {"components": ["bun", "zod@4"]}, "researched": "2026-10-17", "refresh_after": "2027-01-15",
        "summary": "Bun with Zod.", "load_when": "Working on the Bun and Zod service", "targets": {},
        "components": [{"id": component, "original_request": "Zod 4", "effective_constraint": "4", "reason": "user", "resolved": resolved}],
        "integrations": {"zod-bun": {"file": "integration/zod-bun.md"}},
        "verification": {"date": "2026-10-17", "toolchain": {"bun": "1.4.3"}, "commands": ["bun test"],
                         "examples_hash": tree_hash(pack / "examples"),
                         "blocks": {"verified": 0, "exempt_positional": 0, "exempt_explicit": 0},
                         "status": "passed", "limitations": []},
        "review": {"independent": False, "date": "2026-10-17", "open_items": []},
        "builder": {"name": "coding-guidelines-builder", "version": "2.0.0"},
    }
    write(pack / "pack.json", json.dumps(meta, indent=2) + "\n")
    return pack


class PackChecks(unittest.TestCase):
    # Fixtures are built in __init__ rather than setUp: the repo types under Python 3.11, which
    # has no typing.override, and basedpyright recommended mode flags an unmarked setUp override.
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.library: Path = Path(temp.name) / "guidelines"
        self.component: Path = build_component(self.library)
        self.stack: Path = build_stack(self.library)

    def run_packs(self, *args: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "packs.py"), *(str(a) for a in args)],
                              capture_output=True, text=True, check=False)

    def assert_problem(self, needle: str, *args: str | Path) -> None:
        result = self.run_packs(*(args or ("check", self.component)))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(needle, result.stdout)

    def edit(self, path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        _ = path.write_text(text.replace(old, new), encoding="utf-8")

    def meta(self, pack: Path) -> dict[str, object]:
        return cast("dict[str, object]", json.loads((pack / "pack.json").read_text(encoding="utf-8")))

    def save(self, pack: Path, data: dict[str, object]) -> None:
        _ = (pack / "pack.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def test_valid_library_passes_every_check(self) -> None:
        for args in (("check", "--library", self.library), ("check", self.component, self.stack),
                     ("sources", self.component, self.stack)):
            result = self.run_packs(*args)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "verify_examples.py"), str(self.component)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual(tree_hash(self.component / "examples"), self.run_packs("hash", self.component).stdout.strip())

    def test_usage_errors(self) -> None:
        self.assertEqual(2, self.run_packs().returncode)
        self.assertEqual(2, self.run_packs("bogus").returncode)
        self.assertEqual(2, self.run_packs("check", "--nope").returncode)
        self.assertEqual(2, self.run_packs("hash", self.library).returncode)

    def test_coverage_rules(self) -> None:
        data = self.meta(self.component)
        topics = cast("dict[str, object]", data["topics"])
        del topics["testing"]
        self.save(self.component, data)
        self.assert_problem("topic 'testing' from the library checklist is neither covered nor marked na")
        topics["testing"] = {"na": "Nothing to test", "source": "S9"}
        self.save(self.component, data)
        self.assert_problem("practices/testing.md: not referenced by any topic")
        self.assert_problem("cites S9, which is not in sources.md", "sources", self.component)
        topics["testing"] = {"file": "practices/testing.md"}
        topics["bogus"] = {"file": "practices/bogus.md"}
        self.save(self.component, data)
        self.assert_problem("topic 'bogus' is not in the library checklist")

    def test_sub_question_sections(self) -> None:
        self.edit(self.component / "practices/errors.md", "## Failure modes", "## Something else")
        self.assert_problem("no '## Failure modes' section and no na_sections entry")
        data = self.meta(self.component)
        topics = cast("dict[str, dict[str, object]]", data["topics"])
        topics["errors"]["na_sections"] = [{"section": "Failure modes", "reason": "covered elsewhere", "source": "S1"}]
        self.save(self.component, data)
        self.assertEqual(0, self.run_packs("check", self.component).returncode)

    def test_kind_without_checklist(self) -> None:
        data = self.meta(self.component)
        data["kind"] = "framework"
        self.save(self.component, data)
        self.assert_problem("no checklist for kind 'framework'")

    def test_markdown_rules(self) -> None:
        cases: list[tuple[str, str, str, str]] = [
            ("practices/setup.md", "Verified 2026-10-17.\n", "Verified 2026-10-17.\n\n## Empty\n", "empty section 'Empty'"),
            ("practices/setup.md", "Applies to 4.1.0. Verified 2026-10-17.", "Applies whenever.", "needs an 'Applies to"),
            ("practices/setup.md", "### Prefer the documented form for configuration", "Text", "section 'Configuration' needs at least one '### '"),
            ("README.md", "([core](practices/core-api.md))", "([core](examples/src/good.ts))", "link into examples/"),
            ("README.md", "([core](practices/core-api.md))", "([core](practices/missing.md))", "broken link practices/missing.md"),
            ("README.md", "## Most important recent changes", "## Recent", "missing '## Most important recent changes'"),
            ("README.md", "- Trust unparsed data ([errors](practices/errors.md)).", "- Trust unparsed data.", "golden rule must link"),
            ("README.md", "| Resolved | 4.1.0 |", "| Resolved | 4.0.0 |", "header 'Resolved' is '4.0.0'"),
            ("changes.md", "- **Breaking:**", "- Breaking:", "change items start with"),
            ("anti-patterns.md", "**Why:** a cast", "Why: a cast", "AP-1 is missing **Why:**"),
            ("anti-patterns.md", "**Category:** Incorrect", "**Category:** Bad", "Category must be one of"),
            ("sources.md", "| official-docs |", "| blog |", "publisher must be one of"),
        ]
        for name, old, new, needle in cases:
            with self.subTest(name=name, needle=needle):
                original = (self.component / name).read_text(encoding="utf-8")
                self.edit(self.component / name, old, new)
                self.assert_problem(needle)
                _ = (self.component / name).write_text(original, encoding="utf-8")

    def test_byte_hygiene_skill_file_and_examples_hash(self) -> None:
        write(self.component / "practices/setup.md", (self.component / "practices/setup.md").read_text() + "trailing \n")
        self.assert_problem("trailing whitespace")
        write(self.component / "SKILL.md", "# Not allowed\n")
        self.assert_problem("must not contain a SKILL.md")
        (self.component / "SKILL.md").unlink()
        write(self.component / "examples/src/good.ts", "export const ok = 2;\n")
        self.assert_problem("does not match examples/")
        write(self.component / "examples/node_modules/dep/index.js", "x\n")
        self.edit(self.component / "examples/src/good.ts", "2", "1")
        self.assertEqual(tree_hash(self.component / "examples"), cast("dict[str, dict[str, str]]", self.meta(self.component))["verification"]["examples_hash"])

    def test_examples_hash_ignores_build_output_only_at_project_root(self) -> None:
        examples = self.component / "examples"
        before = tree_hash(examples)
        for rel in ("build/out.js", "dist/app.js", "node_modules/x/index.js", "src/__pycache__/m.pyc", "src/node_modules/y.js"):
            write(examples / rel, "generated\n")
        self.assertEqual(before, tree_hash(examples))
        write(examples / "src/build/plugin.ts", "export const plugin = 1;\n")
        self.assertNotEqual(before, tree_hash(examples))
        self.assert_problem("does not match examples/")

    def test_pack_json_rules(self) -> None:
        data = self.meta(self.component)
        data["schema"] = 2
        self.save(self.component, data)
        self.assert_problem("schema 2 is not supported")
        data["schema"] = 1
        data["constraint_source"] = "compat"
        cast("dict[str, object]", data["verification"])["status"] = "partial"
        self.save(self.component, data)
        self.assert_problem("compat-derived constraint needs 'narrowed_by'")
        self.assert_problem("needs its limitations listed")

    def test_stack_rules(self) -> None:
        _ = build_component(self.library, resolved="4.2.0")
        self.assert_problem("edge 'zod-4' records '4.1.0' but the component pack resolves '4.2.0'", "check", self.stack)
        _ = build_component(self.library)
        write(self.stack / "integration/extra.md", "# Extra\n\nApplies to 1. Verified 2026-10-17.\n\n## A\n\n### B\n\nC [S1]\n")
        self.assert_problem("not listed under 'integrations'", "check", self.stack)
        (self.stack / "integration/extra.md").unlink()
        self.edit(self.stack / "README.md", "[zod](../../components/zod-4/README.md)", "zod")
        self.assert_problem("'Components' does not route to components/zod-4/README.md", "check", self.stack)

    def test_citation_rules(self) -> None:
        self.edit(self.component / "practices/setup.md", "recommendation. [S1]", "recommendation.")
        self.assert_problem("cites no source", "sources", self.component)
        self.edit(self.component / "practices/setup.md", "recommendation.", "recommendation. [S7]")
        self.assert_problem("[S7] is not in sources.md", "sources", self.component)
        self.edit(self.component / "practices/setup.md", "[S7]", "[S1]")
        self.edit(self.component / "sources.md", "| official-docs |", "| community |")
        self.assert_problem("rests on community sources only", "sources", self.component)
        self.edit(self.component / "sources.md", "| community |", "| official-docs |")
        self.edit(self.component / "changes.md", "[S2]", "")
        result = self.run_packs("sources", self.component)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("S2 is never cited", result.stdout)
        self.edit(self.component / "changes.md", "use `error`. [S1]", "use `error`.")
        self.assert_problem("change item cites no source", "sources", self.component)

    def test_index_write_check_subset_and_stale(self) -> None:
        self.assertEqual(1, self.run_packs("index", self.library, "--check").returncode)
        self.assertEqual(0, self.run_packs("index", self.library).returncode)
        index = (self.library / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("[`bun-zod`](stacks/bun-zod/README.md)", index)
        self.assertIn("| [`zod-4`](components/zod-4/README.md) | Zod | library | 4.1.0 | 2026-10-17 | 2027-01-15 | bun-zod |", index)
        self.assertEqual(0, self.run_packs("index", self.library, "--check").returncode)
        self.assertEqual(0, self.run_packs("check", "--library", self.library).returncode)
        self.assertEqual(2, self.run_packs("index", self.library, "--only", "stacks/missing").returncode)
        self.assertEqual(0, self.run_packs("index", self.library, "--only", "components/zod-4").returncode)
        self.assertNotIn("bun-zod`]", (self.library / "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual(0, self.run_packs("index", self.library, "--stale", "--today", "2027-01-15").returncode)
        stale = self.run_packs("index", self.library, "--stale", "--today", "2027-01-16")
        self.assertEqual(1, stale.returncode)
        self.assertIn("stale: components/zod-4", stale.stdout)
        _ = build_component(self.library, pack_id="orphan")
        warned = self.run_packs("index", self.library, "--warn-unreferenced", "--referenced", "components/zod-4")
        self.assertIn("components/orphan is not used", warned.stderr)


if __name__ == "__main__":
    _ = unittest.main()
