"""Offline regression tests for the builder's artifact and registry checks."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ArtifactChecks(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.temp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.root: Path = Path(self.temp.name)
        self.skill: Path = self.root / "skill"
        self.examples: Path = self.root / "examples"
        self.skill.mkdir()
        self.examples.mkdir()
        self.addCleanup(self.temp.cleanup)

    def write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(content, encoding="utf-8")

    def run_script(self, name: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / name), *(str(a) for a in args)],
            capture_output=True, text=True, check=False,
        )

    def assert_code(self, expected: int, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)

    def provenance(self, evidence: str = "| SKILL.md | Rules | baseline | m-01 |") -> None:
        self.write(self.skill / "SKILL.md", "# Skill\n\n## Rules\nUse the verified form.\n")
        if "anti-patterns.md" not in evidence:  # the sectionless default table needs a file-level row
            evidence += "\n| references/anti-patterns.md | * | baseline | m-01 |"
        self.write(self.skill / "PROVENANCE.md", "# Provenance\n\n## Evidence\n\n"
                   + "| file | section | evidence | reference |\n|---|---|---|---|\n" + evidence + "\n")
        self.write(self.skill / "references/anti-patterns.md",
                   "# Anti-patterns\n\n| wrong | why | right | grep |\n|---|---|---|---|\n")

    def test_provenance_requires_reference_and_real_tables(self) -> None:
        for row in ("| SKILL.md | Rules | baseline |", "| SKILL.md | Rules | baseline | |"):
            with self.subTest(row=row):
                self.provenance(row)
                self.assert_code(1, self.run_script("check_provenance.py", self.skill))
        self.provenance()
        self.assert_code(0, self.run_script("check_provenance.py", self.skill))
        self.write(self.skill / "references/anti-patterns.md", "# Empty\n")
        self.assert_code(1, self.run_script("check_provenance.py", self.skill))

    def test_provenance_rejects_missing_skill_and_stale_rows(self) -> None:
        self.provenance("| missing.md | Gone | baseline | m-01 |")
        self.assert_code(1, self.run_script("check_provenance.py", self.skill))
        (self.skill / "SKILL.md").unlink()
        self.assert_code(1, self.run_script("check_provenance.py", self.skill))

    def test_headings_inside_nested_fences_are_ignored(self) -> None:
        self.provenance()
        with (self.skill / "SKILL.md").open("a") as stream:
            _ = stream.write("\n````md\n```python\n## Not a section\n```\n````\n")
        self.assert_code(0, self.run_script("check_provenance.py", self.skill))

    def test_provenance_headings_tables_and_structure_tag(self) -> None:
        self.provenance("| SKILL.md | Rules | baseline | m-01 |\n| SKILL.md | Use F# | decision | d-01 |\n"
                        + "| SKILL.md | Routing | structure | layout |\n| references/anti-patterns.md | Contents | structure | layout |")
        with (self.skill / "SKILL.md").open("a") as stream:
            _ = stream.write("\n## Use F#\n\n## Routing ##\n")
        self.write(self.skill / "references/anti-patterns.md",
                   "# Anti-patterns\n\n## Contents\n\n| section | line |\n|---|---|\n| rows | 9 |\n\n"
                   + "| wrong | why | right | grep |\n|---|---|---|---|\n| `a` | b | `c` | `a\\|b` |\n")
        self.assert_code(0, self.run_script("check_provenance.py", self.skill))
        with (self.skill / "references/anti-patterns.md").open("a") as stream:
            _ = stream.write("| `x` | y | `z` | |\n")
        self.assert_code(1, self.run_script("check_provenance.py", self.skill))
        self.provenance("| SKILL.md | Rules | structure | layout |")
        result = self.run_script("check_provenance.py", self.skill)
        self.assert_code(1, result)
        self.assertIn("'structure' is only for", result.stdout)

    def test_provenance_requires_file_level_row_without_sections(self) -> None:
        self.provenance()
        self.write(self.skill / "references/versions.md", "# Versions\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
        result = self.run_script("check_provenance.py", self.skill)
        self.assert_code(1, result)
        self.assertIn("references/versions.md: no sections and no file-level evidence row", result.stdout)
        for section in ("Versions", "*"):
            self.provenance(f"| SKILL.md | Rules | baseline | m-01 |\n| references/versions.md | {section} | compat | v-01 |")
            self.write(self.skill / "references/versions.md", "# Versions\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
            self.assert_code(0, self.run_script("check_provenance.py", self.skill))
        self.write(self.skill / "references/anti-patterns.md",
                   "# Anti-patterns\n\n| wrong | why | right | grep |\n|---|---|---|---|\n| `a|b` | w | r | g |\n")
        result = self.run_script("check_provenance.py", self.skill)
        self.assert_code(1, result)
        self.assertIn("expected 4 cells, got 5", result.stdout)

    def test_audit_layout_and_symlink_escape(self) -> None:
        run = self.root / "run"
        self.write(run / "manifest.md", "# Run\n\n## Additional files\n\n- `notes.txt` scratch\n")
        for rel in ("tasks/check.sh", "tasks/orders/task.md", "baseline/benchmark.json", "baseline/eval-1/without_skill/run-1/grading.json",
                    "research/clones/axum/README.md", "notes.txt"):
            self.write(run / rel, "x\n")
        result = self.run_script("audit_files.py", run)
        self.assert_code(0, result)
        self.assertIn("transient", result.stdout)
        self.write(run / "tasks/stray.md", "x\n")
        self.assert_code(1, self.run_script("audit_files.py", run))
        (run / "tasks/stray.md").unlink()
        (run / "examples").mkdir()
        (run / "examples/link").symlink_to(run / "tasks")
        (run / "examples/broken").symlink_to(run / "missing")
        self.assert_code(0, self.run_script("audit_files.py", run))
        (run / "skill").symlink_to(self.root)
        result = self.run_script("audit_files.py", run)
        self.assert_code(1, result)
        self.assertIn("symlink escapes the run folder: skill", result.stdout)

    def test_token_budget_flags_and_json(self) -> None:
        self.write(self.skill / "SKILL.md", "---\nname: demo\ndescription: short\n---\n# Demo\n")
        self.write(self.skill / "references/big.md", "x" * 24_100)
        self.assert_code(2, self.run_script("token_budget.py", self.skill, "--bogus"))
        result = self.run_script("token_budget.py", self.skill, "--json")
        self.assert_code(1, result)
        report = cast("dict[str, object]", json.loads(result.stdout))
        self.assertEqual(1, report["over_ceiling"])

    def test_examples_fail_missing_unmarked_and_unclosed(self) -> None:
        self.assert_code(2, self.run_script("verify_examples.py", self.skill, self.examples))
        for content in ("```python\nprint(1)\n```\n", "<!-- example: a.py -->\n```python\nprint(1)\n"):
            self.write(self.skill / "SKILL.md", content)
            self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_sync_and_exemptions(self) -> None:
        self.write(self.examples / "a.py", "print(1)\n")
        self.write(self.skill / "SKILL.md", "<!-- example: a.py -->\n```python\nprint(2)\n````\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples))
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples, "--sync"))
        self.assertIn("print(1)", (self.skill / "SKILL.md").read_text())
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))
        self.write(self.skill / "SKILL.md", "<!-- example-exempt: illustrative output -->\n```text\nhello\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_regions_and_markers(self) -> None:
        self.write(self.examples / "src/lib.rs",
                   "fn a() {}\n// region: b\n    fn b() {\n        let region: u8 = 1;\n    }\n// endregion: b\n")
        self.write(self.examples / "config.yaml", "region: us-east-1\nname: x\n")
        self.write(self.skill / "SKILL.md",
                   "<!-- example: src/lib.rs#b -->\n```rust\nold\n```\n\n<!-- example: src/lib.rs -->\n```rust\nold\n```\n\n"
                   + "<!-- example: config.yaml -->\n```yaml\nold\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples, "--sync"))
        synced = (self.skill / "SKILL.md").read_text()
        self.assertIn("```rust\nfn b() {\n    let region: u8 = 1;\n}\n```", synced)
        self.assertIn("```rust\nfn a() {}\n    fn b() {\n", synced)
        self.assertNotIn("// region", synced)
        self.assertIn("```yaml\nregion: us-east-1\nname: x\n```", synced)
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))
        self.write(self.skill / "references/x.md", "<!-- example: src/lib.rs#missing -->\n```rust\nold\n```\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_nested_regions_prose_markers_and_tilde_fences(self) -> None:
        self.write(self.examples / "lib.rs",
                   "// region: outer\nfn outer() {\n    // region: inner\n    let a = 1;\n    // endregion: inner\n}\n// endregion: outer\n")
        self.write(self.examples / "README.md", "# Setup\n\n# region: Config\n\nSet FOO=1\n<!-- region: x -->\nkeep\n<!-- endregion: x -->\n")
        self.write(self.skill / "SKILL.md",
                   "<!-- example: lib.rs#outer -->\n~~~rust\nold\n~~~\n\n<!-- example: README.md -->\n```md\nold\n```\n")
        result = self.run_script("verify_examples.py", self.skill, self.examples, "--sync")
        self.assert_code(0, result)
        self.assertIn("README.md: omitted 2 region marker line(s)", result.stdout)
        synced = (self.skill / "SKILL.md").read_text()
        self.assertIn("~~~rust\nfn outer() {\n    let a = 1;\n}\n~~~", synced)
        self.assertIn("```md\n# Setup\n\n# region: Config\n\nSet FOO=1\nkeep\n```", synced)

    def test_examples_widen_fence_when_source_contains_one(self) -> None:
        self.write(self.examples / "doc.md", "# Readme\n```sh\ncargo run\n```\n")
        self.write(self.skill / "SKILL.md", "<!-- example: doc.md -->\n```md\nold\n```\n")
        result = self.run_script("verify_examples.py", self.skill, self.examples)
        self.assert_code(1, result)
        self.assertIn("widen the fence", result.stdout)
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples, "--sync"))
        self.assertEqual("<!-- example: doc.md -->\n````md\n# Readme\n```sh\ncargo run\n```\n````\n",
                         (self.skill / "SKILL.md").read_text())
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_tolerate_bom_and_reject_deep_closing_indent(self) -> None:
        self.write(self.examples / "a.py", "print(1)\n")
        self.write(self.skill / "SKILL.md", "\ufeff---\nname: demo\n---\n<!-- example: a.py -->\n```python\nprint(1)\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))
        self.write(self.skill / "SKILL.md", "<!-- example: a.py -->\n```python\nprint(1)\n        ```\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_reject_unsupported_markdown_containers(self) -> None:
        for content in ("> ```python\n> print(1)\n> ```\n", "    print(1)\n",
                        "- ```python\n  print(1)\n  ```\n", "> 1. ```python\n> ```\n"):
            with self.subTest(content=content):
                self.write(self.skill / "SKILL.md", content)
                self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples))
        self.write(self.skill / "SKILL.md", "---\nname: demo\nmetadata:\n  nested:\n    value: text\n---\n# Skill\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.skill, self.examples))

    def test_examples_reject_traversal_absolute_and_symlink_sources(self) -> None:
        self.write(self.root / "private.py", "private = True\n")
        (self.examples / "link.py").symlink_to(self.root / "private.py")
        for ref in ("../private.py", str(self.root / "private.py"), "link.py"):
            with self.subTest(ref=ref):
                content = f"<!-- example: {ref} -->\n```python\nold\n```\n"
                self.write(self.skill / "SKILL.md", content)
                self.assert_code(1, self.run_script("verify_examples.py", self.skill, self.examples, "--sync"))
                self.assertEqual(content, (self.skill / "SKILL.md").read_text())

    def test_audit_is_read_only(self) -> None:
        self.write(self.root / "manifest.md", "# Run\n")
        self.write(self.root / "valuable.txt", "keep me\n")
        self.assert_code(1, self.run_script("audit_files.py", self.root))
        self.assert_code(2, self.run_script("audit_files.py", self.root, "--delete"))
        self.assertEqual("keep me\n", (self.root / "valuable.txt").read_text())
        self.assert_code(2, self.run_script("audit_files.py", self.skill))

    def test_description_budget_cannot_be_bypassed_with_folded_yaml(self) -> None:
        for description in (">-\n  " + "x" * 1100, "x" * 1100,
                            "first\n\n  " + "x" * 1100, '"first\n\n  ' + "x" * 1100 + '"',
                            "'first\n\n  " + "x" * 1100 + "'"):
            self.write(self.skill / "SKILL.md", f"---\nname: demo\ndescription: {description}\n---\n")
            self.assert_code(1, self.run_script("token_budget.py", self.skill))

    def test_registry_cli_rejects_malformed_inputs_without_traceback(self) -> None:
        source = self.root / "components.json"
        payloads: list[object] = [[{}], [{"name": [], "registry": None}], [{"name": "x", "registry": "maven", "package": "bad"}]]
        for payload in payloads:
            self.write(source, json.dumps(payload))
            result = self.run_script("registry_versions.py", source)
            self.assert_code(2, result)
            self.assertNotIn("Traceback", result.stderr)
        result = self.run_script("registry_versions.py", source, "--previous")
        self.assert_code(2, result)
        self.assertNotIn("Traceback", result.stderr)


class RegistryChecks(unittest.TestCase):
    def test_stable_candidates_and_errors(self) -> None:
        spec = importlib.util.spec_from_file_location("registry_versions", SCRIPTS / "registry_versions.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # These signatures are defined by the local module loaded from the path above.
        main = cast("Callable[[list[str]], int]", module.main)
        stable = cast("Callable[[str], bool]", module.is_stable)
        latest = cast("Callable[[str, str], str | None]", module.latest)
        self.assertTrue(stable("1.2.3+build.4"))
        self.assertTrue(stable("1.2.post1"))
        self.assertFalse(stable("2.0.0-beta.1"))
        self.assertFalse(stable("1.0rc1"))
        with tempfile.TemporaryDirectory() as temporary:
            components = Path(temporary) / "components.json"
            _ = components.write_text('[{"name":"demo","registry":"npm","package":"demo"}]')
            for candidate, code in (("2.0.0-beta.1", 1), (None, 1), ("1.0.0", 0)):
                with self.subTest(candidate=candidate), patch.object(module, "fetch_json", return_value={"dist-tags": {"latest": candidate}}):
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(code, main(["registry_versions.py", str(components)]))
        with patch.object(module, "fetch_json", return_value={"crate": {"max_version": "2.0.0-beta.1"}}):
            self.assertIsNone(latest("crates", "demo"))
        with patch.object(module, "fetch_json", return_value={"latest_version": "2.0.0-beta.1"}):
            self.assertIsNone(latest("hex", "demo"))
        with patch.object(module, "fetch_json", return_value={
            "info": {"version": "2.0"},
            "releases": {"2.0": [{"yanked": True}], "1.0": [{"yanked": False}], "3.0": []},
        }):
            self.assertEqual("1.0", latest("pypi", "demo"))
        with patch.object(module, "fetch_json", return_value={"dist-tags": {"latest": "3.0.0-rc.1"}, "versions": {"2.1.0": {}, "3.0.0-rc.1": {}}}):
            self.assertEqual("2.1.0", latest("npm", "demo"))

    def test_previous_snapshot_reports_changed_new_and_removed(self) -> None:
        spec = importlib.util.spec_from_file_location("registry_versions", SCRIPTS / "registry_versions.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        main = cast("Callable[[list[str]], int]", module.main)
        with tempfile.TemporaryDirectory() as temporary:
            components = Path(temporary) / "components.json"
            previous = Path(temporary) / "versions-old.json"
            _ = components.write_text('[{"name":"a","registry":"npm","package":"a"},{"name":"b","registry":"npm","package":"b"}]')
            _ = previous.write_text('{"components":[{"name":"a","registry":"npm","package":"a","latest":"1.0.0"},'
                                    + '{"name":"gone","registry":"npm","package":"gone","latest":"0.1.0"}]}')
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(module, "fetch_json", return_value={"dist-tags": {"latest": "2.0.0"}}):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(0, main(["registry_versions.py", str(components), "--previous", str(previous)]))
            snapshot = cast("dict[str, object]", json.loads(stdout.getvalue()))
            entries = cast("list[dict[str, object]]", snapshot["components"])
            self.assertEqual([True, True], [e["changed"] for e in entries])
            self.assertEqual([("1.0.0", "2.0.0"), (None, "2.0.0")], [(e["previous"], e["latest"]) for e in entries])
            self.assertEqual(["gone"], snapshot["removed"])
            self.assertIn("removed: gone (was 0.1.0)", stderr.getvalue())


if __name__ == "__main__":
    _ = unittest.main()
