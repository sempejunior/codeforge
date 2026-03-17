from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from codeforge.domain.entities.agent import AgentSession, AgentType
from codeforge.domain.entities.demand import Demand, LinkedProject
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.sprint import Sprint
from codeforge.domain.entities.story import Story
from codeforge.domain.entities.task import AssigneeType, Task
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.task_id import TaskId
from codeforge.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    init_database,
)
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyAgentSessionRepository,
    SqlAlchemyDemandRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySprintRepository,
    SqlAlchemyStoryRepository,
    SqlAlchemyTaskRepository,
)


@pytest.fixture
async def repositories(tmp_path):
    database_path = tmp_path / "repositories.db"
    database_url = f"sqlite+aiosqlite:///{database_path}"
    engine = create_engine(database_url)
    await init_database(engine)
    session_factory = create_session_factory(engine)

    yield {
        "project": SqlAlchemyProjectRepository(session_factory),
        "task": SqlAlchemyTaskRepository(session_factory),
        "demand": SqlAlchemyDemandRepository(session_factory),
        "story": SqlAlchemyStoryRepository(session_factory),
        "sprint": SqlAlchemySprintRepository(session_factory),
        "agent": SqlAlchemyAgentSessionRepository(session_factory),
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_project_repository_persists_and_lists(repositories: dict[str, object]) -> None:
    repo = repositories["project"]
    assert isinstance(repo, SqlAlchemyProjectRepository)

    project = Project.create(name="backend", path="/tmp/backend")
    await repo.save(project)

    loaded = await repo.get_by_id(project.id)
    assert loaded is not None
    assert loaded.name == "backend"

    by_path = await repo.get_by_path("/tmp/backend")
    assert by_path is not None
    assert by_path.id == project.id

    all_projects = await repo.list_all()
    assert len(all_projects) == 1


@pytest.mark.asyncio
async def test_task_repository_filters_by_status(repositories: dict[str, object]) -> None:
    project_repo = repositories["project"]
    task_repo = repositories["task"]
    assert isinstance(project_repo, SqlAlchemyProjectRepository)
    assert isinstance(task_repo, SqlAlchemyTaskRepository)

    project = Project.create(name="api", path="/tmp/api")
    await project_repo.save(project)

    task, _ = Task.create(project_id=project.id, title="Add endpoint", description="Create route")
    task.assign_to(AssigneeType.AI)
    await task_repo.save(task)

    loaded = await task_repo.get_by_id(task.id)
    assert loaded is not None
    assert loaded.assignee_type == AssigneeType.AI

    filtered = await task_repo.list_by_project(project.id, status=task.status)
    assert len(filtered) == 1
    assert filtered[0].id == task.id


@pytest.mark.asyncio
async def test_demand_repository_roundtrip(repositories: dict[str, object]) -> None:
    project_repo = repositories["project"]
    demand_repo = repositories["demand"]
    assert isinstance(project_repo, SqlAlchemyProjectRepository)
    assert isinstance(demand_repo, SqlAlchemyDemandRepository)

    project = Project.create(name="frontend", path="/tmp/frontend")
    await project_repo.save(project)

    demand, _ = Demand.create(
        title="PIX checkout",
        business_objective="Increase conversion",
        acceptance_criteria=["Must generate QR code"],
        linked_projects=[LinkedProject(project_id=project.id, base_branch="main")],
    )
    await demand_repo.save(demand)

    loaded = await demand_repo.get_by_id(demand.id)
    assert loaded is not None
    assert loaded.title == demand.title
    assert loaded.linked_projects[0].project_id == project.id


@pytest.mark.asyncio
async def test_story_repository_lists_by_demand_and_sprint(
    repositories: dict[str, object],
) -> None:
    demand_repo = repositories["demand"]
    sprint_repo = repositories["sprint"]
    story_repo = repositories["story"]
    assert isinstance(demand_repo, SqlAlchemyDemandRepository)
    assert isinstance(sprint_repo, SqlAlchemySprintRepository)
    assert isinstance(story_repo, SqlAlchemyStoryRepository)

    demand, _ = Demand.create(title="Demand", business_objective="Objective")
    await demand_repo.save(demand)

    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 16),
        end_date=date(2026, 3, 30),
    )
    await sprint_repo.save(sprint)

    story, _ = Story.create(
        demand_id=demand.id,
        title="Implement payment",
        description="Create payment flow",
    )
    story.add_to_sprint(sprint.id)
    await story_repo.save(story)

    by_demand = await story_repo.list_by_demand(demand.id)
    assert len(by_demand) == 1

    by_sprint = await story_repo.list_by_sprint(sprint.id)
    assert len(by_sprint) == 1


@pytest.mark.asyncio
async def test_sprint_repository_get_active(repositories: dict[str, object]) -> None:
    repo = repositories["sprint"]
    assert isinstance(repo, SqlAlchemySprintRepository)

    sprint, _ = Sprint.create(
        name="Sprint Active",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 15),
    )
    sprint.start()
    await repo.save(sprint)

    active = await repo.get_active()
    assert active is not None
    assert active.id == sprint.id


@pytest.mark.asyncio
async def test_agent_session_repository_roundtrip(repositories: dict[str, object]) -> None:
    repo = repositories["agent"]
    assert isinstance(repo, SqlAlchemyAgentSessionRepository)

    task_id = str(TaskId.generate())
    session = AgentSession(
        id="session-1",
        task_id=task_id,
        agent_type=AgentType.CODER,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
    )
    session.steps_executed = 5
    session.tool_call_count = 2
    session.started_at = datetime.now(UTC)
    await repo.save(session)

    loaded = await repo.get_by_id("session-1")
    assert loaded is not None
    assert loaded.steps_executed == 5

    by_task = await repo.list_by_task_id(TaskId(task_id))
    assert len(by_task) == 1
