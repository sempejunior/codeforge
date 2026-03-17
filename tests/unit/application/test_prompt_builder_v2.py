from __future__ import annotations

from pathlib import Path

from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.domain.entities.agent import AgentType


def test_skills_injected_in_system_prompt():
    prompt = build_system_prompt(
        AgentType.CODER,
        skills=["Always use Tailwind.", "No CSS modules."],
    )
    assert "## Project Instructions" in prompt
    assert "Always use Tailwind." in prompt
    assert "No CSS modules." in prompt


def test_memory_entries_injected_before_skills():
    prompt = build_system_prompt(
        AgentType.CODER,
        memory_entries=["Architecture: clean arch."],
        skills=["Use ruff."],
    )
    memory_pos = prompt.index("## Project Memory")
    skills_pos = prompt.index("## Project Instructions")
    assert memory_pos < skills_pos


def test_extra_context_comes_after_skills():
    prompt = build_system_prompt(
        AgentType.CODER,
        skills=["Use ruff."],
        extra_context="Task: fix login bug.",
    )
    skills_pos = prompt.index("## Project Instructions")
    context_pos = prompt.index("## Additional Context")
    assert skills_pos < context_pos


def test_no_skills_no_memory_unchanged_behavior():
    prompt_plain = build_system_prompt(AgentType.CODER, project_path=Path("/proj"))
    prompt_explicit = build_system_prompt(
        AgentType.CODER,
        project_path=Path("/proj"),
        skills=None,
        memory_entries=None,
    )
    assert prompt_plain == prompt_explicit


def test_multiple_skills_separated_by_divider():
    prompt = build_system_prompt(
        AgentType.QA_REVIEWER,
        skills=["Rule 1", "Rule 2"],
    )
    assert "---" in prompt
    idx1 = prompt.index("Rule 1")
    idx2 = prompt.index("Rule 2")
    assert idx1 < idx2
