from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeforge.domain.entities.agent import AgentSession, AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.agent_memory import AgentMemory
from codeforge.domain.entities.agent_skill import AgentSkill
from codeforge.domain.entities.demand import Demand, DemandStatus, GenerationStatus, LinkedProject
from codeforge.domain.entities.project import CodeReviewMode, Project, ProjectConfig
from codeforge.domain.entities.repository import AnalysisStatus, Repository, RepositoryStatus
from codeforge.domain.entities.sprint import Sprint, SprintMetrics, SprintStatus
from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.entities.task import (
    AssigneeType,
    ExecutionProgress,
    Task,
    TaskSource,
    TaskStatus,
)
from codeforge.domain.entities.team import Team
from codeforge.domain.entities.team_document import (
    TeamDocument,
    TeamDocumentKind,
    TeamDocumentSource,
)
from codeforge.domain.ports.agent_memory_repository import AgentMemoryRepositoryPort
from codeforge.domain.ports.agent_skill_repository import AgentSkillRepositoryPort
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.sprint_repository import SprintRepositoryPort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.ports.team_document_repository import TeamDocumentRepositoryPort
from codeforge.domain.ports.team_repository import TeamRepositoryPort
from codeforge.domain.value_objects.complexity import ComplexityTier
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId
from codeforge.domain.value_objects.team_document_id import TeamDocumentId
from codeforge.domain.value_objects.team_id import TeamId

from .models import (
    AgentMemoryModel,
    AgentSessionModel,
    AgentSkillModel,
    DemandModel,
    ProjectModel,
    RepositoryModel,
    SprintModel,
    StoryModel,
    TaskExecutionModel,
    TaskModel,
    TaskReviewModel,
    TeamDocumentModel,
    TeamModel,
)


class SqlAlchemyTeamRepository(TeamRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, team: Team) -> None:
        async with self._session_factory() as session:
            existing = await session.get(TeamModel, str(team.id))
            if existing is None:
                existing = TeamModel(id=str(team.id))
                session.add(existing)
            existing.name = team.name
            existing.description = team.description
            existing.created_at = _as_utc(team.created_at)
            existing.updated_at = _as_utc(team.updated_at)
            await session.commit()

    async def get_by_id(self, team_id: TeamId) -> Team | None:
        async with self._session_factory() as session:
            model = await session.get(TeamModel, str(team_id))
            return _to_team(model)

    async def list_all(self) -> list[Team]:
        async with self._session_factory() as session:
            stmt = select(TeamModel).order_by(TeamModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [team for model in models if (team := _to_team(model)) is not None]

    async def delete(self, team_id: TeamId) -> None:
        async with self._session_factory() as session:
            model = await session.get(TeamModel, str(team_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyTeamDocumentRepository(TeamDocumentRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, document: TeamDocument) -> None:
        async with self._session_factory() as session:
            existing = await session.get(TeamDocumentModel, str(document.id))
            if existing is None:
                existing = TeamDocumentModel(id=str(document.id))
                session.add(existing)
            existing.team_id = str(document.team_id)
            existing.parent_id = str(document.parent_id) if document.parent_id else None
            existing.title = document.title
            existing.kind = document.kind.value
            existing.content = document.content
            existing.linked_project_id = (
                str(document.linked_project_id) if document.linked_project_id else None
            )
            existing.linked_repository_id = (
                str(document.linked_repository_id) if document.linked_repository_id else None
            )
            existing.source = document.source.value
            existing.created_at = _as_utc(document.created_at)
            existing.updated_at = _as_utc(document.updated_at)
            await session.commit()

    async def get_by_id(self, document_id: TeamDocumentId) -> TeamDocument | None:
        async with self._session_factory() as session:
            model = await session.get(TeamDocumentModel, str(document_id))
            return _to_team_document(model)

    async def list_by_team(self, team_id: TeamId) -> list[TeamDocument]:
        async with self._session_factory() as session:
            stmt = (
                select(TeamDocumentModel)
                .where(TeamDocumentModel.team_id == str(team_id))
                .order_by(TeamDocumentModel.created_at.asc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [doc for model in models if (doc := _to_team_document(model)) is not None]

    async def list_by_project(self, project_id: ProjectId) -> list[TeamDocument]:
        async with self._session_factory() as session:
            stmt = (
                select(TeamDocumentModel)
                .where(TeamDocumentModel.linked_project_id == str(project_id))
                .order_by(TeamDocumentModel.created_at.asc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [doc for model in models if (doc := _to_team_document(model)) is not None]

    async def find_generated_context_document(
        self,
        team_id: TeamId,
        project_id: ProjectId,
    ) -> TeamDocument | None:
        async with self._session_factory() as session:
            stmt = select(TeamDocumentModel).where(
                TeamDocumentModel.team_id == str(team_id),
                TeamDocumentModel.linked_project_id == str(project_id),
                TeamDocumentModel.source == TeamDocumentSource.GENERATED.value,
                TeamDocumentModel.kind == TeamDocumentKind.DOCUMENT.value,
                TeamDocumentModel.title == "Contexto Gerado",
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_team_document(model)

    async def list_by_repository(self, repository_id: RepositoryId) -> list[TeamDocument]:
        async with self._session_factory() as session:
            stmt = (
                select(TeamDocumentModel)
                .where(TeamDocumentModel.linked_repository_id == str(repository_id))
                .order_by(TeamDocumentModel.created_at.asc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [doc for model in models if (doc := _to_team_document(model)) is not None]

    async def find_generated_repo_context_document(
        self,
        team_id: TeamId,
        repository_id: RepositoryId,
    ) -> TeamDocument | None:
        async with self._session_factory() as session:
            stmt = select(TeamDocumentModel).where(
                TeamDocumentModel.team_id == str(team_id),
                TeamDocumentModel.linked_repository_id == str(repository_id),
                TeamDocumentModel.source == TeamDocumentSource.GENERATED.value,
                TeamDocumentModel.kind == TeamDocumentKind.DOCUMENT.value,
                TeamDocumentModel.title == "Contexto Gerado",
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_team_document(model)

    async def find_folder_for_project(
        self,
        team_id: TeamId,
        project_id: ProjectId,
    ) -> TeamDocument | None:
        async with self._session_factory() as session:
            stmt = select(TeamDocumentModel).where(
                TeamDocumentModel.team_id == str(team_id),
                TeamDocumentModel.linked_project_id == str(project_id),
                TeamDocumentModel.kind == TeamDocumentKind.FOLDER.value,
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_team_document(model)

    async def find_folder_for_repository(
        self,
        team_id: TeamId,
        repository_id: RepositoryId,
    ) -> TeamDocument | None:
        async with self._session_factory() as session:
            stmt = select(TeamDocumentModel).where(
                TeamDocumentModel.team_id == str(team_id),
                TeamDocumentModel.linked_repository_id == str(repository_id),
                TeamDocumentModel.kind == TeamDocumentKind.FOLDER.value,
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_team_document(model)

    async def delete(self, document_id: TeamDocumentId) -> None:
        async with self._session_factory() as session:
            model = await session.get(TeamDocumentModel, str(document_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


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
            existing.team_id = str(project.team_id) if project.team_id else None
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

    async def list_all(self) -> list[Project]:
        async with self._session_factory() as session:
            stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [project for model in models if (project := _to_project(model)) is not None]

    async def list_by_team(self, team_id: TeamId) -> list[Project]:
        async with self._session_factory() as session:
            stmt = (
                select(ProjectModel)
                .where(ProjectModel.team_id == str(team_id))
                .order_by(ProjectModel.created_at.desc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [project for model in models if (project := _to_project(model)) is not None]

    async def delete(self, project_id: ProjectId) -> None:
        async with self._session_factory() as session:
            model = await session.get(ProjectModel, str(project_id))
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyRepositoryStore(RepositoryStorePort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, repository: Repository) -> None:
        async with self._session_factory() as session:
            existing = await session.get(RepositoryModel, str(repository.id))
            if existing is None:
                existing = RepositoryModel(id=str(repository.id))
                session.add(existing)
            existing.project_id = str(repository.project_id)
            existing.name = repository.name
            existing.slug = repository.slug
            existing.repo_url = repository.repo_url
            existing.default_branch = repository.default_branch
            existing.path = repository.path
            existing.status = repository.status.value
            existing.context_doc = repository.context_doc
            existing.analysis_status = repository.analysis_status.value
            existing.analysis_executor = repository.analysis_executor
            existing.analysis_error = repository.analysis_error
            existing.local_path_hint = repository.local_path_hint
            existing.created_at = _as_utc(repository.created_at)
            existing.updated_at = _as_utc(repository.updated_at)
            await session.commit()

    async def get_by_id(self, repository_id: RepositoryId) -> Repository | None:
        async with self._session_factory() as session:
            model = await session.get(RepositoryModel, str(repository_id))
            return _to_repository(model)

    async def list_by_project(self, project_id: ProjectId) -> list[Repository]:
        async with self._session_factory() as session:
            stmt = (
                select(RepositoryModel)
                .where(RepositoryModel.project_id == str(project_id))
                .order_by(RepositoryModel.created_at.asc())
            )
            models = (await session.execute(stmt)).scalars().all()
            return [
                repository
                for model in models
                if (repository := _to_repository(model)) is not None
            ]

    async def list_all(self) -> list[Repository]:
        async with self._session_factory() as session:
            stmt = select(RepositoryModel).order_by(RepositoryModel.created_at.desc())
            models = (await session.execute(stmt)).scalars().all()
            return [
                repository
                for model in models
                if (repository := _to_repository(model)) is not None
            ]

    async def get_by_repo_url(self, repo_url: str) -> Repository | None:
        async with self._session_factory() as session:
            stmt = select(RepositoryModel).where(RepositoryModel.repo_url == repo_url)
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_repository(model)

    async def delete(self, repository_id: RepositoryId) -> None:
        async with self._session_factory() as session:
            model = await session.get(RepositoryModel, str(repository_id))
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
            existing.pr_url = task.pr_url
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
            existing.team_id = str(demand.team_id) if demand.team_id else None
            existing.acceptance_criteria = list(demand.acceptance_criteria)
            existing.linked_projects = [
                {
                    "project_id": str(project.project_id),
                    "base_branch": project.base_branch,
                }
                for project in demand.linked_projects
            ]
            existing.status = demand.status.value
            existing.generation_status = demand.generation_status.value
            existing.generation_error = demand.generation_error
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
            existing.project_id = str(story.project_id) if story.project_id else None
            existing.sprint_id = str(story.sprint_id) if story.sprint_id else None
            existing.title = story.title
            existing.description = story.description
            existing.acceptance_criteria = list(story.acceptance_criteria)
            existing.technical_references = list(story.technical_references)
            existing.repository_ids = [str(repository_id) for repository_id in story.repository_ids]
            existing.linked_projects = [str(project_id) for project_id in story.linked_projects]
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

    async def list_all(self, limit: int = 100) -> list[AgentSession]:
        async with self._session_factory() as session:
            stmt = (
                select(AgentSessionModel)
                .order_by(AgentSessionModel.started_at.desc())
                .limit(limit)
            )
            models = (await session.execute(stmt)).scalars().all()
            return [
                session_obj
                for model in models
                if (session_obj := _to_agent_session(model)) is not None
            ]


class SqlAlchemyTaskExecutionRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self,
        task_id: TaskId,
        success: bool,
        exit_code: int,
        output: str,
        changed_files: list[str],
        diff: str,
    ) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = select(TaskExecutionModel).where(TaskExecutionModel.task_id == str(task_id))
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                existing = TaskExecutionModel(task_id=str(task_id), created_at=now, updated_at=now)
                session.add(existing)
            existing.success = success
            existing.exit_code = exit_code
            existing.output = output
            existing.changed_files = changed_files
            existing.diff = diff
            existing.updated_at = now
            await session.commit()

    async def get_by_task_id(self, task_id: TaskId) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            stmt = select(TaskExecutionModel).where(TaskExecutionModel.task_id == str(task_id))
            model = (await session.execute(stmt)).scalar_one_or_none()
            if model is None:
                return None
            return {
                "task_id": model.task_id,
                "success": model.success,
                "exit_code": model.exit_code,
                "output": model.output,
                "changed_files": list(model.changed_files),
                "diff": model.diff,
                "created_at": _as_utc(model.created_at),
                "updated_at": _as_utc(model.updated_at),
            }


class SqlAlchemyTaskReviewRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self,
        task_id: TaskId,
        verdict: str,
        summary: str,
        issues: list[dict[str, str]],
    ) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = select(TaskReviewModel).where(TaskReviewModel.task_id == str(task_id))
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                existing = TaskReviewModel(task_id=str(task_id), created_at=now, updated_at=now)
                session.add(existing)
            existing.verdict = verdict
            existing.summary = summary
            existing.issues = issues
            existing.updated_at = now
            await session.commit()

    async def get_by_task_id(self, task_id: TaskId) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            stmt = select(TaskReviewModel).where(TaskReviewModel.task_id == str(task_id))
            model = (await session.execute(stmt)).scalar_one_or_none()
            if model is None:
                return None
            return {
                "task_id": model.task_id,
                "verdict": model.verdict,
                "summary": model.summary,
                "issues": list(model.issues),
                "created_at": _as_utc(model.created_at),
                "updated_at": _as_utc(model.updated_at),
            }


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
        team_id=TeamId(model.team_id) if model.team_id else None,
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
        pr_url=model.pr_url,
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
        team_id=TeamId(model.team_id) if model.team_id else None,
        status=DemandStatus(model.status),
        generation_status=GenerationStatus(model.generation_status),
        generation_error=model.generation_error,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_story(model: StoryModel | None) -> Story | None:
    if model is None:
        return None
    return Story(
        id=StoryId(model.id),
        demand_id=DemandId(model.demand_id),
        project_id=ProjectId(model.project_id) if model.project_id else None,
        title=model.title,
        description=model.description,
        acceptance_criteria=list(model.acceptance_criteria),
        technical_references=list(model.technical_references),
        repository_ids=[RepositoryId(repository_id) for repository_id in model.repository_ids],
        linked_projects=[ProjectId(project_id) for project_id in model.linked_projects],
        sprint_id=SprintId(model.sprint_id) if model.sprint_id else None,
        status=StoryStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_repository(model: RepositoryModel | None) -> Repository | None:
    if model is None:
        return None
    return Repository(
        id=RepositoryId(model.id),
        project_id=ProjectId(model.project_id),
        name=model.name,
        slug=model.slug,
        repo_url=model.repo_url,
        default_branch=model.default_branch,
        path=model.path,
        status=RepositoryStatus(model.status),
        context_doc=model.context_doc,
        analysis_status=AnalysisStatus(model.analysis_status),
        analysis_executor=model.analysis_executor,
        analysis_error=model.analysis_error,
        local_path_hint=model.local_path_hint,
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


class SqlAlchemyAgentSkillRepository(AgentSkillRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, skill: AgentSkill) -> None:
        async with self._session_factory() as session:
            existing = await session.get(AgentSkillModel, skill.id)
            if existing is None:
                existing = AgentSkillModel(id=skill.id)
                session.add(existing)
            existing.name = skill.name
            existing.content = skill.content
            existing.always_active = skill.always_active
            existing.project_id = str(skill.project_id) if skill.project_id else None
            existing.agent_type = skill.agent_type.value if skill.agent_type else None
            existing.created_at = _as_utc(skill.created_at)
            existing.updated_at = _as_utc(skill.updated_at)
            await session.commit()

    async def get(self, skill_id: str) -> AgentSkill | None:
        async with self._session_factory() as session:
            model = await session.get(AgentSkillModel, skill_id)
            return _to_agent_skill(model)

    async def list_for_agent(
        self,
        project_id: ProjectId | None,
        agent_type: AgentType | None,
        only_active: bool = True,
    ) -> list[AgentSkill]:
        async with self._session_factory() as session:
            stmt = select(AgentSkillModel)
            if only_active:
                stmt = stmt.where(AgentSkillModel.always_active.is_(True))
            if project_id is not None:
                stmt = stmt.where(
                    or_(
                        AgentSkillModel.project_id.is_(None),
                        AgentSkillModel.project_id == str(project_id),
                    )
                )
            else:
                stmt = stmt.where(AgentSkillModel.project_id.is_(None))
            if agent_type is not None:
                stmt = stmt.where(
                    or_(
                        AgentSkillModel.agent_type.is_(None),
                        AgentSkillModel.agent_type == agent_type.value,
                    )
                )
            models = (await session.execute(stmt)).scalars().all()
            return [skill for model in models if (skill := _to_agent_skill(model)) is not None]

    async def list_by_project(self, project_id: ProjectId) -> list[AgentSkill]:
        async with self._session_factory() as session:
            stmt = select(AgentSkillModel).where(
                AgentSkillModel.project_id == str(project_id)
            )
            models = (await session.execute(stmt)).scalars().all()
            return [skill for model in models if (skill := _to_agent_skill(model)) is not None]

    async def delete(self, skill_id: str) -> None:
        async with self._session_factory() as session:
            model = await session.get(AgentSkillModel, skill_id)
            if model is not None:
                await session.delete(model)
                await session.commit()


class SqlAlchemyAgentMemoryRepository(AgentMemoryRepositoryPort):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, memory: AgentMemory) -> None:
        async with self._session_factory() as session:
            existing = await session.get(AgentMemoryModel, memory.id)
            if existing is None:
                stmt = select(AgentMemoryModel).where(
                    AgentMemoryModel.project_id == str(memory.project_id),
                    AgentMemoryModel.key == memory.key,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                existing = AgentMemoryModel(id=memory.id)
                session.add(existing)
            existing.project_id = str(memory.project_id)
            existing.key = memory.key
            existing.content = memory.content
            existing.updated_at = _as_utc(memory.updated_at)
            await session.commit()

    async def get(self, project_id: ProjectId, key: str) -> AgentMemory | None:
        async with self._session_factory() as session:
            stmt = select(AgentMemoryModel).where(
                AgentMemoryModel.project_id == str(project_id),
                AgentMemoryModel.key == key,
            )
            model = (await session.execute(stmt)).scalar_one_or_none()
            return _to_agent_memory(model)

    async def list_for_project(self, project_id: ProjectId) -> list[AgentMemory]:
        async with self._session_factory() as session:
            stmt = select(AgentMemoryModel).where(
                AgentMemoryModel.project_id == str(project_id)
            )
            models = (await session.execute(stmt)).scalars().all()
            return [mem for model in models if (mem := _to_agent_memory(model)) is not None]

    async def delete(self, memory_id: str) -> None:
        async with self._session_factory() as session:
            model = await session.get(AgentMemoryModel, memory_id)
            if model is not None:
                await session.delete(model)
                await session.commit()


def _to_agent_skill(model: AgentSkillModel | None) -> AgentSkill | None:
    if model is None:
        return None
    return AgentSkill(
        id=model.id,
        name=model.name,
        content=model.content,
        always_active=model.always_active,
        project_id=ProjectId(model.project_id) if model.project_id else None,
        agent_type=AgentType(model.agent_type) if model.agent_type else None,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_team(model: TeamModel | None) -> Team | None:
    if model is None:
        return None
    return Team(
        id=TeamId(model.id),
        name=model.name,
        description=model.description,
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_team_document(model: TeamDocumentModel | None) -> TeamDocument | None:
    if model is None:
        return None
    return TeamDocument(
        id=TeamDocumentId(model.id),
        team_id=TeamId(model.team_id),
        title=model.title,
        kind=TeamDocumentKind(model.kind),
        parent_id=TeamDocumentId(model.parent_id) if model.parent_id else None,
        content=model.content,
        linked_project_id=ProjectId(model.linked_project_id) if model.linked_project_id else None,
        linked_repository_id=RepositoryId(model.linked_repository_id) if model.linked_repository_id else None,
        source=TeamDocumentSource(model.source),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
    )


def _to_agent_memory(model: AgentMemoryModel | None) -> AgentMemory | None:
    if model is None:
        return None
    return AgentMemory(
        id=model.id,
        project_id=ProjectId(model.project_id),
        key=model.key,
        content=model.content,
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
