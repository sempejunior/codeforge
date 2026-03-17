from __future__ import annotations

import time

import pytest

from codeforge.domain.entities.agent_memory import AgentMemory
from codeforge.domain.value_objects.project_id import ProjectId


def _pid() -> ProjectId:
    return ProjectId.generate()


def test_create_sets_fields():
    pid = _pid()
    mem = AgentMemory.create(id="m1", project_id=pid, key="conventions", content="# Rules")
    assert mem.id == "m1"
    assert mem.project_id == pid
    assert mem.key == "conventions"
    assert mem.content == "# Rules"
    assert mem.updated_at is not None


def test_update_changes_content_and_updated_at():
    pid = _pid()
    mem = AgentMemory.create(id="m1", project_id=pid, key="k", content="old")
    before = mem.updated_at
    time.sleep(0.001)
    mem.update("new content")
    assert mem.content == "new content"
    assert mem.updated_at > before


def test_update_does_not_change_key_or_project():
    pid = _pid()
    mem = AgentMemory.create(id="m1", project_id=pid, key="arch", content="old")
    mem.update("new")
    assert mem.key == "arch"
    assert mem.project_id == pid


def test_different_keys_are_independent():
    pid = _pid()
    m1 = AgentMemory.create(id="m1", project_id=pid, key="k1", content="a")
    m2 = AgentMemory.create(id="m2", project_id=pid, key="k2", content="b")
    m1.update("updated")
    assert m2.content == "b"


def test_create_with_same_key_different_project():
    p1 = _pid()
    p2 = _pid()
    m1 = AgentMemory.create(id="m1", project_id=p1, key="stack", content="react")
    m2 = AgentMemory.create(id="m2", project_id=p2, key="stack", content="vue")
    assert m1.content != m2.content
