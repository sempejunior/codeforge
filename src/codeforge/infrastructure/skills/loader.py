from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import yaml


class SkillsLoader:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir

    def list_available(self) -> list[dict[str, str | bool]]:
        results: list[dict[str, str | bool]] = []
        if not self._skills_dir.exists():
            return results

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            meta = self._parse_frontmatter(skill_file)
            available, missing = self._check_requirements(meta)
            results.append({
                "name": meta.get("name", skill_dir.name),
                "description": meta.get("description", ""),
                "available": available,
                "missing": missing,
            })
        return results

    def load(self, name: str) -> str | None:
        skill_file = self._skills_dir / name / "SKILL.md"
        if not skill_file.exists():
            return None
        content = skill_file.read_text(encoding="utf-8")
        return self._strip_frontmatter(content)

    def load_raw(self, name: str) -> str | None:
        skill_file = self._skills_dir / name / "SKILL.md"
        if not skill_file.exists():
            return None
        return skill_file.read_text(encoding="utf-8")

    def find_first_available(self, category: str) -> str | None:
        if not self._skills_dir.exists():
            return None

        for skill_dir in sorted(self._skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            meta = self._parse_frontmatter(skill_file)
            if meta.get("category") != category:
                continue

            available, _ = self._check_requirements(meta)
            if available:
                return meta.get("name", skill_dir.name)

        return None

    def get_metadata(self, name: str) -> dict:
        skill_file = self._skills_dir / name / "SKILL.md"
        if not skill_file.exists():
            return {}
        return self._parse_frontmatter(skill_file)

    def _parse_frontmatter(self, skill_file: Path) -> dict:
        content = skill_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return {}
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}
        try:
            return yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return {}

    def _strip_frontmatter(self, content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def _check_requirements(self, meta: dict) -> tuple[bool, str]:
        requires = meta.get("requires", {})
        if not isinstance(requires, dict):
            return True, ""

        missing_parts: list[str] = []
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing_parts.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing_parts.append(f"ENV: {env}")

        return len(missing_parts) == 0, ", ".join(missing_parts)
