"""Validate the published skill paths, their unified frontmatter layout, index and references."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
skills = [root / path for path in tracked if re.fullmatch(r"[^/]+/[^/]+/SKILL\.md", path)]
errors: list[str] = []
index = (root / "README.md").read_text()
if not skills:
    errors.append("No published skills found")
for path in skills:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        errors.append(f"{path.relative_to(root)}: missing frontmatter")
        continue
    fields = {m[1]: m[2] for m in re.finditer(r"^([a-z][a-z0-9_-]*):[ \t]*(.*)$", parts[1], re.M)}
    if fields.get("name", "").strip("\"'") != path.parent.name:
        errors.append(f"{path.relative_to(root)}: name must match directory")
    if not fields.get("description") or fields["description"] in {"|", ">", "|-", ">-"}:
        errors.append(f"{path.relative_to(root)}: description must be a single line")
    keys = re.findall(r"^([a-z][a-z0-9_-]*):", parts[1], re.M)
    layout = ["name", "description", "license"] + (["compatibility"] if "compatibility" in fields else []) + ["metadata"]
    if keys != layout:
        errors.append(f"{path.relative_to(root)}: frontmatter keys must be {', '.join(layout)} in that order")
    # The repository is AGPL-3.0; a skill adapted from elsewhere keeps its own LICENSE and license.
    license_ok = {"AGPL-3.0"} | ({"MIT"} if (path.parent / "LICENSE").is_file() else set())
    if fields.get("license", "").strip("\"'") not in license_ok:
        errors.append(f"{path.relative_to(root)}: unexpected license")
    meta = {m[1]: m[2].strip("\"'") for m in re.finditer(r"^  ([a-z][a-z0-9_-]*):[ \t]*(.+)$", parts[1], re.M)}
    meta_keys = list(meta)
    if meta_keys not in (["author", "version", "vendor"], ["author", "version", "vendor", "upstream"]):
        errors.append(f"{path.relative_to(root)}: metadata keys must be author, version, vendor[, upstream] in that order")
    if meta.get("author") != "edbfi":
        errors.append(f"{path.relative_to(root)}: metadata author must be edbfi")
    if not re.fullmatch(r"\d+\.\d+\.\d+", meta.get("version", "")):
        errors.append(f"{path.relative_to(root)}: metadata version must be semver")
    if meta.get("vendor") != path.parent.parent.name:
        errors.append(f"{path.relative_to(root)}: vendor must match namespace")
    if f"({path.relative_to(root)})" not in index:
        errors.append(f"{path.relative_to(root)}: missing README index entry")
    for target in {m[0] for m in re.finditer(r"references/[A-Za-z0-9_./-]+\.md", parts[2])}:
        if not (path.parent / target).is_file():
            errors.append(f"{path.relative_to(root)}: missing {target}")
for target in (m[1] for m in re.finditer(r"\]\(([^)]+/SKILL\.md)\)", index)):
    if not (root / target).is_file():
        errors.append(f"README.md: missing {target}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Validated {len(skills)} skill entry points, metadata, index and reference paths")
