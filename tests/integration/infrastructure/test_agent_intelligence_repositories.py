from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codeforge.domain.entities.agent import AgentType
from codeforge.domain.entities.agent_memory import AgentMemory
from codeforge.domain.entities.agent_skill import AgentSkill
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.infrastructure.persistence.models import Base
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyAgentMemoryRepository,
    SqlAlchemyAgentSkillRepository,
)

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def skill_repo(session_factory):
    return SqlAlchemyAgentSkillRepository(session_factory)


@pytest_asyncio.fixture
async def memory_repo(session_factory):
    return SqlAlchemyAgentMemoryRepository(session_factory)


@pytest.mark.asyncio
async def test_save_and_get_skill(skill_repo):
    skill = AgentSkill.create(id="s1", name="Style", content="Use Tailwind.")
    await skill_repo.save(skill)
    loaded = await skill_repo.get("s1")
    assert loaded is not None
    assert loaded.name == "Style"
    assert loaded.content == "Use Tailwind."


@pytest.mark.asyncio
async def test_list_for_agent_includes_global_and_project(skill_repo):
    pid = ProjectId.generate()
    global_skill = AgentSkill.create(id="g1", name="Global", content="Always type hints.")
    project_skill = AgentSkill.create(
        id="p1", name="Project", content="Use FastAPI.", project_id=pid
    )
    await skill_repo.save(global_skill)
    await skill_repo.save(project_skill)

    results = await skill_repo.list_for_agent(project_id=pid, agent_type=None)
    ids = {s.id for s in results}
    assert "g1" in ids
    assert "p1" in ids


@pytest.mark.asyncio
async def test_list_for_agent_filters_inactive(skill_repo):
    pid = ProjectId.generate()
    active = AgentSkill.create(id="a1", name="Active", content="x", always_active=True)
    inactive = AgentSkill.create(id="i1", name="Inactive", content="y", always_active=False)
    await skill_repo.save(active)
    await skill_repo.save(inactive)

    results = await skill_repo.list_for_agent(project_id=None, agent_type=None, only_active=True)
    ids = {s.id for s in results}
    assert "a1" in ids
    assert "i1" not in ids


@pytest.mark.asyncio
async def test_delete_skill(skill_repo):
    skill = AgentSkill.create(id="del1", name="Temp", content="x")
    await skill_repo.save(skill)
    await skill_repo.delete("del1")
    assert await skill_repo.get("del1") is None


@pytest.mark.asyncio
async def test_memory_upsert_by_key(memory_repo):
    pid = ProjectId.generate()
    mem = AgentMemory.create(id="m1", project_id=pid, key="arch", content="Clean arch.")
    await memory_repo.save(mem)

    loaded = await memory_repo.get(pid, "arch")
    assert loaded is not None
    assert loaded.content == "Clean arch."

    loaded.update("Updated arch.")
    await memory_repo.save(loaded)

    reloaded = await memory_repo.get(pid, "arch")
    assert reloaded is not None
    assert reloaded.content == "Updated arch."
