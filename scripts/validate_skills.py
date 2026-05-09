#!/usr/bin/env python3
"""Validate skill folder conventions for this repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    data: dict[str, str] = {}
    index = 1
    while index < len(lines) and lines[index].strip() != "---":
        line = lines[index]
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
        index += 1
    return data


def get_skill_dirs(root: Path) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.exists():
        return []
    return sorted(path for path in skills_root.iterdir() if path.is_dir())


def validate_skill_dir(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_dir}: missing SKILL.md"]

    contents = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(contents)
    name = fm.get("name", "")
    description = fm.get("description", "")

    if not name:
        errors.append(f"{skill_md}: frontmatter missing 'name'")
    if not description:
        errors.append(f"{skill_md}: frontmatter missing 'description'")
    if name and name != skill_dir.name:
        errors.append(f"{skill_md}: name '{name}' does not match folder '{skill_dir.name}'")
    if name and not NAME_RE.match(name):
        errors.append(f"{skill_md}: name '{name}' must be lowercase hyphen-case")

    for match in SKILL_LINK_RE.findall(contents):
        if not match.startswith("references/"):
            continue
        target = skill_dir / match
        if not target.exists():
            errors.append(f"{skill_md}: referenced file does not exist: {match}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skill_dirs = get_skill_dirs(root)
    if not skill_dirs:
        print("No skill directories found under skills/.")
        return 1

    all_errors: list[str] = []
    for skill_dir in skill_dirs:
        all_errors.extend(validate_skill_dir(skill_dir))

    if all_errors:
        print("Skill validation failed:")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print(f"Skill validation passed for {len(skill_dirs)} skill(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
