"""Offline tests for verify_examples.py and audit_files.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class ArtifactChecks(unittest.TestCase):
    # Fixtures are built in __init__ rather than setUp: the repo types under Python 3.11, which
    # has no typing.override, and basedpyright recommended mode flags an unmarked setUp override.
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root: Path = Path(temp.name)
        self.pack: Path = self.root / "pack"
        self.examples: Path = self.root / "examples"
        self.pack.mkdir()
        self.examples.mkdir()

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

    def test_audit_layout_and_symlink_escape(self) -> None:
        run = self.root / "run"
        self.write(run / "manifest.md", "# Run\n\n## Additional files\n\n- `notes.txt` scratch\n")
        for rel in ("components.json", "versions.json", "facts/ts.md", "outline/ts.md", "review/ts.md",
                    "draft/components/ts/README.md", "logs/verify.log", "clones/ts/README.md", "notes.txt"):
            self.write(run / rel, "x\n")
        result = self.run_script("audit_files.py", run)
        self.assert_code(0, result)
        self.assertIn("transient", result.stdout)
        self.write(run / "tasks/stray.md", "x\n")
        self.assert_code(1, self.run_script("audit_files.py", run))
        (run / "tasks/stray.md").unlink()
        (run / "tasks").rmdir()
        (run / "draft/link").symlink_to(run / "facts")
        (run / "draft/broken").symlink_to(run / "missing")
        self.assert_code(0, self.run_script("audit_files.py", run))
        (run / "logs/escape").symlink_to(self.root)
        result = self.run_script("audit_files.py", run)
        self.assert_code(1, result)
        self.assertIn("symlink escapes the run folder: logs/escape", result.stdout)
        self.assertIn("declare it under '## Additional files'", result.stdout)
        self.write(run / "manifest.md", "# Run\n\n## Additional files\n\n- `notes.txt` scratch\n- `logs/escape` linked output\n")
        self.assert_code(0, self.run_script("audit_files.py", run))

    def test_examples_fail_missing_unmarked_and_unclosed(self) -> None:
        self.assert_code(2, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        for content in ("```python\nprint(1)\n```\n", "<!-- example: a.py -->\n```python\nprint(1)\n"):
            self.write(self.pack / "README.md", content)
            self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_examples_sync_and_exemptions(self) -> None:
        self.write(self.examples / "a.py", "print(1)\n")
        self.write(self.pack / "README.md", "<!-- example: a.py -->\n```python\nprint(2)\n````\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync"))
        self.assertIn("print(1)", (self.pack / "README.md").read_text())
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.write(self.pack / "README.md", "<!-- example-exempt: illustrative output -->\n```text\nhello\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_examples_regions_and_markers(self) -> None:
        self.write(self.examples / "src/lib.rs",
                   "fn a() {}\n// region: b\n    fn b() {\n        let region: u8 = 1;\n    }\n// endregion: b\n")
        self.write(self.examples / "config.yaml", "region: us-east-1\nname: x\n")
        self.write(self.pack / "README.md",
                   "<!-- example: src/lib.rs#b -->\n```rust\nold\n```\n\n<!-- example: src/lib.rs -->\n```rust\nold\n```\n\n"
                   + "<!-- example: config.yaml -->\n```yaml\nold\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync"))
        synced = (self.pack / "README.md").read_text()
        self.assertIn("```rust\nfn b() {\n    let region: u8 = 1;\n}\n```", synced)
        self.assertIn("```rust\nfn a() {}\n    fn b() {\n", synced)
        self.assertNotIn("// region", synced)
        self.assertIn("```yaml\nregion: us-east-1\nname: x\n```", synced)
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.write(self.pack / "practices/x.md", "<!-- example: src/lib.rs#missing -->\n```rust\nold\n```\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.write(self.examples / "dup.rs", "// region: a\nx\n// endregion: a\n// region: a\ny\n// endregion: a\n")
        self.write(self.pack / "practices/x.md", "<!-- example: dup.rs#a -->\n```rust\nold\n```\n")
        result = self.run_script("verify_examples.py", self.pack, "--examples", self.examples)
        self.assert_code(1, result)
        self.assertIn("starts twice", result.stdout)
        self.write(self.examples / "blank.py", "a = 1\n\nb = 2\n")
        self.write(self.pack / "practices/x.md", " <!-- example: blank.py -->\n ```python\n old\n ```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync"))
        self.assertEqual(" <!-- example: blank.py -->\n ```python\n a = 1\n\n b = 2\n ```\n", (self.pack / "practices/x.md").read_text())

    def test_examples_nested_regions_prose_markers_and_tilde_fences(self) -> None:
        self.write(self.examples / "lib.rs",
                   "// region: outer\nfn outer() {\n    // region: inner\n    let a = 1;\n    // endregion: inner\n}\n// endregion: outer\n")
        self.write(self.examples / "README.md", "# Setup\n\n# region: Config\n\nSet FOO=1\n<!-- region: x -->\nkeep\n<!-- endregion: x -->\n")
        self.write(self.pack / "README.md",
                   "<!-- example: lib.rs#outer -->\n~~~rust\nold\n~~~\n\n<!-- example: README.md -->\n```md\nold\n```\n")
        result = self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync")
        self.assert_code(0, result)
        self.assertIn("README.md: omitted 2 region marker line(s)", result.stdout)
        synced = (self.pack / "README.md").read_text()
        self.assertIn("~~~rust\nfn outer() {\n    let a = 1;\n}\n~~~", synced)
        self.assertIn("```md\n# Setup\n\n# region: Config\n\nSet FOO=1\nkeep\n```", synced)

    def test_examples_sync_reports_unwritten_files(self) -> None:
        self.write(self.examples / "a.py", "print(1)\n")
        content = "<!-- example: a.py -->\n```python\nold\n```\n\n```python\nunmarked = 1\n```\n"
        self.write(self.pack / "README.md", content)
        result = self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync")
        self.assert_code(1, result)
        self.assertIn("a.py: not written (0 unresolved, 1 unmarked block(s) in this file)", result.stdout)
        self.assertNotIn(": synced", result.stdout)
        self.assertEqual(content, (self.pack / "README.md").read_text())

    def test_examples_widen_fence_when_source_contains_one(self) -> None:
        self.write(self.examples / "doc.md", "# Readme\n```sh\ncargo run\n```\n")
        self.write(self.pack / "README.md", "<!-- example: doc.md -->\n```md\nold\n```\n")
        result = self.run_script("verify_examples.py", self.pack, "--examples", self.examples)
        self.assert_code(1, result)
        self.assertIn("widen the fence", result.stdout)
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync"))
        self.assertEqual("<!-- example: doc.md -->\n````md\n# Readme\n```sh\ncargo run\n```\n````\n",
                         (self.pack / "README.md").read_text())
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_examples_tolerate_bom_and_reject_deep_closing_indent(self) -> None:
        self.write(self.examples / "a.py", "print(1)\n")
        self.write(self.pack / "README.md", "\ufeff---\nname: demo\n---\n<!-- example: a.py -->\n```python\nprint(1)\n```\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.write(self.pack / "README.md", "<!-- example: a.py -->\n```python\nprint(1)\n        ```\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_examples_reject_unsupported_markdown_containers(self) -> None:
        for content in ("> ```python\n> print(1)\n> ```\n", "    print(1)\n",
                        "- ```python\n  print(1)\n  ```\n", "> 1. ```python\n> ```\n"):
            with self.subTest(content=content):
                self.write(self.pack / "README.md", content)
                self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))
        self.write(self.pack / "README.md", "---\nname: demo\nmetadata:\n  nested:\n    value: text\n---\n# Skill\n")
        self.assert_code(0, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_positional_exemptions_and_counts(self) -> None:
        self.write(self.examples / "good.ts", "export const ok = 1;\n")
        self.write(self.pack / "README.md", "# Demo\n\n```sh\nbun test\n```\n")
        self.write(self.pack / "changes.md", "# Changes\n\n## 1.0\n\n```ts\nold.api();\n```\n")
        self.write(self.pack / "anti-patterns.md", "# AP\n\n## AP-1: x\n\n**Don't:** call it\n```ts\nbad();\n```\n"
                   + "**Do instead:** this\n<!-- example: good.ts -->\n```ts\nexport const ok = 1;\n```\n")
        self.write(self.examples / "skip.md", "```ts\nignored\n```\n")
        result = self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--json")
        self.assert_code(0, result)
        counts = cast("dict[str, dict[str, int]]", json.loads(result.stdout.strip().splitlines()[-1]))
        self.assertEqual({"verified": 1, "exempt_positional": 3, "exempt_explicit": 0}, counts["blocks"])
        self.write(self.pack / "practices/x.md", "# X\n\n**Why:** wrong\n```ts\nbad();\n```\n")
        self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples))

    def test_examples_reject_traversal_absolute_and_symlink_sources(self) -> None:
        self.write(self.root / "private.py", "private = True\n")
        (self.examples / "link.py").symlink_to(self.root / "private.py")
        for ref in ("../private.py", str(self.root / "private.py"), "link.py"):
            with self.subTest(ref=ref):
                content = f"<!-- example: {ref} -->\n```python\nold\n```\n"
                self.write(self.pack / "README.md", content)
                self.assert_code(1, self.run_script("verify_examples.py", self.pack, "--examples", self.examples, "--sync"))
                self.assertEqual(content, (self.pack / "README.md").read_text())

    def test_audit_is_read_only(self) -> None:
        self.write(self.root / "manifest.md", "# Run\n")
        self.write(self.root / "valuable.txt", "keep me\n")
        self.assert_code(1, self.run_script("audit_files.py", self.root))
        self.assert_code(2, self.run_script("audit_files.py", self.root, "--delete"))
        self.assertEqual("keep me\n", (self.root / "valuable.txt").read_text())
        self.assert_code(2, self.run_script("audit_files.py", self.pack))

if __name__ == "__main__":
    _ = unittest.main()
