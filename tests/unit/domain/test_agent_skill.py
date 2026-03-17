from __future__ import annotations

import time

import pytest

from codeforge.domain.entities.agent import AgentType
from codeforge.domain.entities.agent_skill import AgentSkill
from codeforge.domain.value_objects.project_id import ProjectId


def _make_skill(**kwargs) -> AgentSkill:
    defaults = {
        "id": "skill-1",
        "name": "Style guide",
        "content": "Always use Tailwind.",
    }
    defaults.update(kwargs)
    return AgentSkill.create(**defaults)


def test_create_sets_defaults():
    skill = _make_skill()
    assert skill.always_active is True
    assert skill.project_id is None
    assert skill.agent_type is None
    assert skill.created_at == skill.updated_at


def test_create_with_project_and_agent_type():
    pid = ProjectId.generate()
    skill = _make_skill(project_id=pid, agent_type=AgentType.CODER)
    assert skill.project_id == pid
    assert skill.agent_type == AgentType.CODER


def test_update_content_changes_updated_at():
    skill = _make_skill()
    before = skill.updated_at
    time.sleep(0.001)
    skill.update_content("New content")
    assert skill.content == "New content"
    assert skill.updated_at > before


def test_update_partial_fields():
    skill = _make_skill()
    skill.update(name="Updated name", always_active=False)
    assert skill.name == "Updated name"
    assert skill.always_active is False
    assert skill.content == "Always use Tailwind."


def test_update_with_no_args_only_bumps_updated_at():
    skill = _make_skill()
    original_name = skill.name
    time.sleep(0.001)
    skill.update()
    assert skill.name == original_name
    assert skill.updated_at > skill.created_at


def test_global_skill_has_no_project_id():
    skill = AgentSkill.create(id="g1", name="Global", content="Always...", project_id=None)
    assert skill.project_id is None
