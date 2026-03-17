from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeforge.domain.entities.agent import AgentSession, AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.demand import Demand, DemandStatus, LinkedProject
from codeforge.domain.entities.project import CodeReviewMode, Project, ProjectConfig
from codeforge.domain.entities.sprint import Sprint, SprintMetrics, SprintStatus
from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.entities.task import (
    AssigneeType,
    ExecutionProgress,
    Task,
    TaskSource,
    TaskStatus,
)
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.sprint_repository import SprintRepositoryPort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.value_objects.complexity import ComplexityTier
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId

from .models import (
    AgentSessionModel,
    DemandModel,
    ProjectModel,
    SprintModel,
    StoryModel,
    TaskModel,
)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class SqlAlchemyProjectRepository(ProjectRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, project: Project) -> None:
        async with self._session_factory() as session:
            existing = await session.get(ProjectModel, str(project.id))
            if existing is None:
                existing = ProjectModel(id=str(project.id))
                session.add(existing)
            existing.name = project.name
            existing.path = project.path
            existing.repo_url = project.repo_url
            existing.default_branch = project.default_branch
            existing.max_parallel_subtasks = project.config.max_parallel_subtasks
            existing.max_qa_cycles = project.config.max_qa_cycles
            existing.max_subtask_retries = project.config.max_subtask_retries
            existing.auto_continue_delay_seconds = project.config.auto_continue_delay_seconds
            existing.default_model = project.config.default_model
            existing.code_review_mode = project.config.code_review_mode.value
            existing.human_review_required = project.config.human_review_required
            existing.auto_start_tasks = project.config.auto_start_tasks
            existing.breakdown_requires_approval = project.config.breakdown_requires_approval
            existing.auto_merge = project.config.auto_merge
            existing.created_at = _as_utc(project.created_at)
            existing.updated_at = _as_utc(project.updated_at)
            await session.commit()

    async def get_by_id(self, project_id: ProjectId) -> Project | None:
        async with self._session_factory() as session:
            model = await session.get(ProjectModel, str(project_id))
            return _to_project(model)

    async def get_by_path(self, path: str) -> Project | None:
        async with self._session_factory() as session:
            stmt = select(ProjectModel).where(ProjectModel.path == path)
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_project(model)

    async def list_all(self) -> list[Project]:
        async with self._session_factory() as session:
            stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [project for model in models if (project := _to_project(model)) is not None]

    async def delete(self, project_id: ProjectId) -> None:
        async with self._session_factory() as session:
            model = await session.get(ProjectModel, str(project_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyTaskRepository(TaskRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, task: Task) -> None:
        async with self._session_factory() as session:
            existing = await session.get(TaskModel, str(task.id))
            if existing is None:
                existing = TaskModel(id=str(task.id))
                session.add(existing)
            existing.project_id = str(task.project_id)
            existing.story_id = str(task.story_id) if task.story_id else None
            existing.title = task.title
            existing.description = task.description
            existing.status = task.status.value
            existing.complexity = task.complexity.value if task.complexity else None
            existing.assignee_type = task.assignee_type.value
            existing.source = task.source.value
            existing.source_ref = task.source_ref
            existing.worktree_path = task.worktree_path
            existing.branch_name = task.branch_name
            existing.error_message = task.error_message
            existing.execution_progress = {
                "current_phase": task.execution_progress.current_phase,
                "total_subtasks": task.execution_progress.total_subtasks,
                "completed_subtasks": task.execution_progress.completed_subtasks,
                "failed_subtasks": task.execution_progress.failed_subtasks,
                "current_subtask_id": task.execution_progress.current_subtask_id,
                "qa_cycle": task.execution_progress.qa_cycle,
                "steps_executed": task.execution_progress.steps_executed,
            }
            existing.created_at = _as_utc(task.created_at)
            existing.updated_at = _as_utc(task.updated_at)
            await session.commit()

    async def get_by_id(self, task_id: TaskId) -> Task | None:
        async with self._session_factory() as session:
            model = await session.get(TaskModel, str(task_id))
            return _to_task(model)

    async def list_by_project(
        self,
        project_id: ProjectId,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        async with self._session_factory() as session:
            stmt = select(TaskModel).where(TaskModel.project_id == str(project_id))
            if status is not None:
                stmt = stmt.where(TaskModel.status == status.value)
            stmt = stmt.order_by(TaskModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [task for model in models if (task := _to_task(model)) is not None]

    async def delete(self, task_id: TaskId) -> None:
        async with self._session_factory() as session:
            model = await session.get(TaskModel, str(task_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyDemandRepository(DemandRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, demand: Demand) -> None:
        async with self._session_factory() as session:
            existing = await session.get(DemandModel, str(demand.id))
            if existing is None:
                existing = DemandModel(id=str(demand.id))
                session.add(existing)
            existing.title = demand.title
            existing.business_objective = demand.business_objective
            existing.acceptance_criteria = list(demand.acceptance_criteria)
            existing.linked_projects = [
                {
                    "project_id": str(project.project_id),
                    "base_branch": project.base_branch,
                }
                for project in demand.linked_projects
            ]
            existing.status = demand.status.value
            existing.created_at = _as_utc(demand.created_at)
            existing.updated_at = _as_utc(demand.updated_at)
            await session.commit()

    async def get_by_id(self, demand_id: DemandId) -> Demand | None:
        async with self._session_factory() as session:
            model = await session.get(DemandModel, str(demand_id))
            return _to_demand(model)

    async def list_all(self, status: DemandStatus | None = None) -> list[Demand]:
        async with self._session_factory() as session:
            stmt = select(DemandModel)
            if status is not None:
                stmt = stmt.where(DemandModel.status == status.value)
            stmt = stmt.order_by(DemandModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [demand for model in models if (demand := _to_demand(model)) is not None]

    async def delete(self, demand_id: DemandId) -> None:
        async with self._session_factory() as session:
            model = await session.get(DemandModel, str(demand_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyStoryRepository(StoryRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, story: Story) -> None:
        async with self._session_factory() as session:
            existing = await session.get(StoryModel, str(story.id))
            if existing is None:
                existing = StoryModel(id=str(story.id))
                session.add(existing)
            existing.demand_id = str(story.demand_id)
            existing.sprint_id = str(story.sprint_id) if story.sprint_id else None
            existing.title = story.title
            existing.description = story.description
            existing.acceptance_criteria = list(story.acceptance_criteria)
            existing.status = story.status.value
            existing.created_at = _as_utc(story.created_at)
            existing.updated_at = _as_utc(story.updated_at)
            await session.commit()

    async def get_by_id(self, story_id: StoryId) -> Story | None:
        async with self._session_factory() as session:
            model = await session.get(StoryModel, str(story_id))
            return _to_story(model)

    async def list_by_demand(
        self,
        demand_id: DemandId,
        status: StoryStatus | None = None,
    ) -> list[Story]:
        async with self._session_factory() as session:
            stmt = select(StoryModel).where(StoryModel.demand_id == str(demand_id))
            if status is not None:
                stmt = stmt.where(StoryModel.status == status.value)
            stmt = stmt.order_by(StoryModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [story for model in models if (story := _to_story(model)) is not None]

    async def list_by_sprint(self, sprint_id: SprintId) -> list[Story]:
        async with self._session_factory() as session:
            stmt = (
                select(StoryModel)
                .where(StoryModel.sprint_id == str(sprint_id))
                .order_by(StoryModel.created_at.desc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [story for model in models if (story := _to_story(model)) is not None]

    async def delete(self, story_id: StoryId) -> None:
        async with self._session_factory() as session:
            model = await session.get(StoryModel, str(story_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemySprintRepository(SprintRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, sprint: Sprint) -> None:
        async with self._session_factory() as session:
            existing = await session.get(SprintModel, str(sprint.id))
            if existing is None:
                existing = SprintModel(id=str(sprint.id))
                session.add(existing)
            existing.name = sprint.name
            existing.start_date = sprint.start_date
            existing.end_date = sprint.end_date
            existing.story_ids = [str(story_id) for story_id in sprint.story_ids]
            existing.status = sprint.status.value
            existing.metrics = {
                "tasks_done": sprint.metrics.tasks_done,
                "tasks_total": sprint.metrics.tasks_total,
                "stories_done": sprint.metrics.stories_done,
                "stories_total": sprint.metrics.stories_total,
            }
            existing.created_at = _as_utc(sprint.created_at)
            existing.updated_at = _as_utc(sprint.updated_at)
            await session.commit()

    async def get_by_id(self, sprint_id: SprintId) -> Sprint | None:
        async with self._session_factory() as session:
            model = await session.get(SprintModel, str(sprint_id))
            return _to_sprint(model)

    async def list_all(self, status: SprintStatus | None = None) -> list[Sprint]:
        async with self._session_factory() as session:
            stmt = select(SprintModel)
            if status is not None:
                stmt = stmt.where(SprintModel.status == status.value)
            stmt = stmt.order_by(SprintModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [sprint for model in models if (sprint := _to_sprint(model)) is not None]

    async def get_active(self) -> Sprint | None:
        async with self._session_factory() as session:
            stmt = select(SprintModel).where(SprintModel.status == SprintStatus.ACTIVE.value)
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_sprint(model)

    async def delete(self, sprint_id: SprintId) -> None:
        async with self._session_factory() as session:
            model = await session.get(SprintModel, str(sprint_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyAgentSessionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, agent_session: AgentSession) -> None:
        async with self._session_factory() as session:
            existing = await session.get(AgentSessionModel, agent_session.id)
            if existing is None:
                existing = AgentSessionModel(id=agent_session.id)
                session.add(existing)
            existing.task_id = agent_session.task_id
            existing.agent_type = agent_session.agent_type.value
            existing.model = str(agent_session.model)
            existing.outcome = agent_session.outcome.value if agent_session.outcome else None
            existing.steps_executed = agent_session.steps_executed
            existing.tool_call_count = agent_session.tool_call_count
            existing.usage = {
                "input_tokens": agent_session.usage.input_tokens,
                "output_tokens": agent_session.usage.output_tokens,
                "cache_read_tokens": agent_session.usage.cache_read_tokens,
                "cache_write_tokens": agent_session.usage.cache_write_tokens,
            }
            existing.error = agent_session.error
            existing.started_at = _as_utc(agent_session.started_at)
            existing.ended_at = _as_utc(agent_session.ended_at) if agent_session.ended_at else None
            await session.commit()

    async def get_by_id(self, session_id: str) -> AgentSession | None:
        async with self._session_factory() as session:
            model = await session.get(AgentSessionModel, session_id)
            return _to_agent_session(model)

    async def list_by_task_id(self, task_id: TaskId) -> list[AgentSession]:
        async with self._session_factory() as session:
            stmt = (
                select(AgentSessionModel)
                .where(AgentSessionModel.task_id == str(task_id))
                .order_by(AgentSessionModel.started_at.desc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [
                session_obj
                for model in models
                if (session_obj := _to_agent_session(model)) is not None
            ]


def _to_project(model: ProjectModel | None) -> Project | None:
    if model is None:
        return None
    config = ProjectConfig(
        max_parallel_subtasks=model.max_parallel_subtasks,
        max_qa_cycles=model.max_qa_cycles,
        max_subtask_retries=model.max_subtask_retries,
        auto_continue_delay_seconds=model.auto_continue_delay_seconds,
        default_model=model.default_model,
        code_review_mode=CodeReviewMode(model.code_review_mode),
        human_review_required=model.human_review_required,
        auto_start_tasks=model.auto_start_tasks,
        breakdown_requires_approval=model.breakdown_requires_approval,
        auto_merge=model.auto_merge,
    )
    return Project(
        id=ProjectId(model.id),
        name=model.name,
        path=model.path,
        repo_url=model.repo_url,
        default_branch=model.default_branch,
        config=config,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_task(model: TaskModel | None) -> Task | None:
    if model is None:
        return None
    progress_data = model.execution_progress or {}
    progress = ExecutionProgress(
        current_phase=progress_data.get("current_phase", ""),
        total_subtasks=int(progress_data.get("total_subtasks", 0)),
        completed_subtasks=int(progress_data.get("completed_subtasks", 0)),
        failed_subtasks=int(progress_data.get("failed_subtasks", 0)),
        current_subtask_id=progress_data.get("current_subtask_id"),
        qa_cycle=int(progress_data.get("qa_cycle", 0)),
        steps_executed=int(progress_data.get("steps_executed", 0)),
    )
    return Task(
        id=TaskId(model.id),
        project_id=ProjectId(model.project_id),
        title=model.title,
        description=model.description,
        status=TaskStatus(model.status),
        complexity=ComplexityTier(model.complexity) if model.complexity else None,
        execution_progress=progress,
        story_id=StoryId(model.story_id) if model.story_id else None,
        assignee_type=AssigneeType(model.assignee_type),
        source=TaskSource(model.source),
        source_ref=model.source_ref,
        worktree_path=model.worktree_path,
        branch_name=model.branch_name,
        error_message=model.error_message,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_demand(model: DemandModel | None) -> Demand | None:
    if model is None:
        return None
    linked_projects = [
        LinkedProject(
            project_id=ProjectId(project["project_id"]),
            base_branch=project.get("base_branch", "main"),
        )
        for project in model.linked_projects
    ]
    return Demand(
        id=DemandId(model.id),
        title=model.title,
        business_objective=model.business_objective,
        acceptance_criteria=list(model.acceptance_criteria),
        linked_projects=linked_projects,
        status=DemandStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_story(model: StoryModel | None) -> Story | None:
    if model is None:
        return None
    return Story(
        id=StoryId(model.id),
        demand_id=DemandId(model.demand_id),
        title=model.title,
        description=model.description,
        acceptance_criteria=list(model.acceptance_criteria),
        sprint_id=SprintId(model.sprint_id) if model.sprint_id else None,
        status=StoryStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_sprint(model: SprintModel | None) -> Sprint | None:
    if model is None:
        return None
    metrics_data = model.metrics or {}
    metrics = SprintMetrics(
        tasks_done=int(metrics_data.get("tasks_done", 0)),
        tasks_total=int(metrics_data.get("tasks_total", 0)),
        stories_done=int(metrics_data.get("stories_done", 0)),
        stories_total=int(metrics_data.get("stories_total", 0)),
    )
    return Sprint(
        id=SprintId(model.id),
        name=model.name,
        start_date=model.start_date,
        end_date=model.end_date,
        story_ids=[StoryId(story_id) for story_id in model.story_ids],
        status=SprintStatus(model.status),
        metrics=metrics,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_agent_session(model: AgentSessionModel | None) -> AgentSession | None:
    if model is None:
        return None
    usage_data = model.usage or {}
    usage = TokenUsage(
        input_tokens=int(usage_data.get("input_tokens", 0)),
        output_tokens=int(usage_data.get("output_tokens", 0)),
        cache_read_tokens=int(usage_data.get("cache_read_tokens", 0)),
        cache_write_tokens=int(usage_data.get("cache_write_tokens", 0)),
    )
    return AgentSession(
        id=model.id,
        task_id=model.task_id,
        agent_type=AgentType(model.agent_type),
        model=ModelId(model.model),
        outcome=SessionOutcome(model.outcome) if model.outcome else None,
        steps_executed=model.steps_executed,
        tool_call_count=model.tool_call_count,
        usage=usage,
        error=model.error,
        started_at=_as_utc(model.started_at),
        ended_at=_as_utc(model.ended_at) if model.ended_at else None,
    )
