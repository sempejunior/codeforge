from __future__ import annotations

from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.domain.entities.agent import AgentType


def test_prompt_returned_for_each_agent_type():
    for agent_type in AgentType:
        prompt = build_system_prompt(agent_type)
        assert isinstance(prompt, str)
        assert len(prompt) > 10


def test_prompt_includes_project_path(tmp_path):
    prompt = build_system_prompt(AgentType.CODER, project_path=tmp_path)
    assert str(tmp_path) in prompt


def test_prompt_includes_extra_context():
    extra = "Extra context here"
    prompt = build_system_prompt(AgentType.PLANNER, extra_context=extra)
    assert extra in prompt


def test_coder_prompt_has_expected_content():
    prompt = build_system_prompt(AgentType.CODER)
    assert "subtask" in prompt.lower() or "implement" in prompt.lower()


def test_qa_reviewer_prompt_mentions_qa_report():
    prompt = build_system_prompt(AgentType.QA_REVIEWER)
    assert "qa_report" in prompt.lower() or "qa report" in prompt.lower()
