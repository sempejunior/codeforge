from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from codeforge.infrastructure.skills.loader import SkillsLoader


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    skill_a = tmp_path / "skill-a"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text(
        "---\n"
        "name: skill-a\n"
        "description: Skill A description\n"
        "category: testing\n"
        "requires:\n"
        "  bins: [\"python3\"]\n"
        "---\n"
        "\n# Skill A\n\nBody content here.\n"
    )

    skill_b = tmp_path / "skill-b"
    skill_b.mkdir()
    (skill_b / "SKILL.md").write_text(
        "---\n"
        "name: skill-b\n"
        "description: Skill B needs missing binary\n"
        "category: testing\n"
        "requires:\n"
        "  bins: [\"nonexistent-binary-xyz\"]\n"
        "---\n"
        "\n# Skill B\n\nBody.\n"
    )

    skill_c = tmp_path / "skill-c"
    skill_c.mkdir()
    (skill_c / "SKILL.md").write_text(
        "---\n"
        "name: skill-c\n"
        "description: Skill C needs env var\n"
        "category: analyze-codebase\n"
        "requires:\n"
        '  env: ["MISSING_ENV_VAR_XYZ"]\n'
        "---\n"
        "\n# Skill C\n\nBody.\n"
    )

    return tmp_path


def test_list_available_filters_by_bins(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    results = loader.list_available()

    names = {r["name"] for r in results if r["available"]}
    assert "skill-a" in names
    assert "skill-b" not in names


def test_list_available_marks_missing(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    results = loader.list_available()

    skill_b = next(r for r in results if r["name"] == "skill-b")
    assert skill_b["available"] is False
    assert "CLI: nonexistent-binary-xyz" in str(skill_b["missing"])


def test_list_available_env_missing(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    results = loader.list_available()

    skill_c = next(r for r in results if r["name"] == "skill-c")
    assert skill_c["available"] is False
    assert "ENV: MISSING_ENV_VAR_XYZ" in str(skill_c["missing"])


def test_list_available_env_present(skills_dir: Path) -> None:
    with patch.dict(os.environ, {"MISSING_ENV_VAR_XYZ": "value"}):
        loader = SkillsLoader(skills_dir)
        results = loader.list_available()
        skill_c = next(r for r in results if r["name"] == "skill-c")
        assert skill_c["available"] is True


def test_find_first_available_returns_match(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    result = loader.find_first_available("testing")
    assert result == "skill-a"


def test_find_first_available_returns_none_when_no_match(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    result = loader.find_first_available("analyze-codebase")
    assert result is None


def test_find_first_available_nonexistent_category(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    result = loader.find_first_available("nonexistent")
    assert result is None


def test_load_returns_content_without_frontmatter(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    content = loader.load("skill-a")
    assert content is not None
    assert "---" not in content
    assert "# Skill A" in content
    assert "Body content here." in content


def test_load_returns_none_for_missing_skill(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    assert loader.load("nonexistent-skill") is None


def test_load_raw_includes_frontmatter(skills_dir: Path) -> None:
    loader = SkillsLoader(skills_dir)
    content = loader.load_raw("skill-a")
    assert content is not None
    assert content.startswith("---")
    assert "name: skill-a" in content


def test_empty_skills_dir(tmp_path: Path) -> None:
    loader = SkillsLoader(tmp_path)
    assert loader.list_available() == []
    assert loader.find_first_available("anything") is None


def test_nonexistent_skills_dir() -> None:
    loader = SkillsLoader(Path("/nonexistent/path"))
    assert loader.list_available() == []
    assert loader.find_first_available("anything") is None
