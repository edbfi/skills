"""Validate the published skill paths and their documented frontmatter subset."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
skills = [root / path for path in tracked if re.fullmatch(r"[^/]+/[^/]+/SKILL\.md", path)]
errors = []
index = (root / "README.md").read_text()
if not skills:
    errors.append("No published skills found")
for path in skills:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        errors.append(f"{path.relative_to(root)}: missing frontmatter")
        continue
    fields = dict(re.findall(r"^([a-z]+):[ \t]*(.*)$", parts[1], re.M))
    if fields.get("name", "").strip("\"'") != path.parent.name:
        errors.append(f"{path.relative_to(root)}: name must match directory")
    if not fields.get("description") or fields["description"] in {"|", ">", "|-", ">-"}:
        errors.append(f"{path.relative_to(root)}: description must be a single line")
    if "license" in fields and fields["license"].strip("\"'") != "AGPL-3.0":
        errors.append(f"{path.relative_to(root)}: unexpected license")
    vendor = re.search(r"^  vendor:[ \t]*(.+)$", parts[1], re.M)
    if vendor and vendor[1].strip("\"'") != path.parent.parent.name:
        errors.append(f"{path.relative_to(root)}: vendor must match namespace")
    if f"({path.relative_to(root)})" not in index:
        errors.append(f"{path.relative_to(root)}: missing README index entry")
    for target in set(re.findall(r"references/[A-Za-z0-9_./-]+\.md", parts[2])):
        if not (path.parent / target).is_file():
            errors.append(f"{path.relative_to(root)}: missing {target}")
for target in re.findall(r"\]\(([^)]+/SKILL\.md)\)", index):
    if not (root / target).is_file():
        errors.append(f"README.md: missing {target}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Validated {len(skills)} skill entry points, metadata, index and reference paths")
