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


if __name__ == "__main__":
    _ = unittest.main()
