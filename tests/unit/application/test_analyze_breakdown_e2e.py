from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from codeforge.application.use_cases.run_breakdown import (
    BreakdownInput,
    run_breakdown,
)
from codeforge.application.use_cases.run_repository_analysis import (
    AnalysisInput,
    run_repository_analysis,
)
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.entities.task import Task
from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.ports.ai_provider import (
    AIProviderPort,
    GenerateResult,
    StreamPart,
)
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.task_repository import TaskRepositoryPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId

CONTEXT_DOC = """\
# Project Architecture
## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 async
- Frontend: React 19, Tailwind CSS 4
- DB: PostgreSQL (prod) / SQLite (dev)

## Key Files
- src/api/routers/users.py — user CRUD endpoints
- src/domain/entities/user.py — User dataclass
- src/infrastructure/persistence/user_repo.py — SqlAlchemyUserRepository

## Patterns
- Clean Architecture: domain <- application <- infrastructure <- api
- Async I/O everywhere
- Pydantic schemas in API layer, dataclasses in domain
"""

BREAKDOWN_JSON = """\
{
  "tasks": [
    {
      "title": "Add email verification field to User entity",
      "description": "Update src/domain/entities/user.py to add email_verified: bool field",
      "acceptance_criteria": ["User dataclass has email_verified field"],
      "depends_on_titles": []
    },
    {
      "title": "Add verification endpoint to users router",
      "description": "Update src/api/routers/users.py following existing CRUD pattern",
      "acceptance_criteria": ["POST /api/users/{id}/verify returns 200"],
      "depends_on_titles": ["Add email verification field to User entity"]
    }
  ]
}
"""


class _InMemoryRepositoryStore(RepositoryStorePort):
    def __init__(self) -> None:
        self._repositories: dict[str, Repository] = {}

    async def save(self, repository: Repository) -> None:
        self._repositories[str(repository.id)] = repository

    async def get_by_id(self, repository_id: RepositoryId) -> Repository | None:
        return self._repositories.get(str(repository_id))

    async def list_by_project(self, project_id: ProjectId) -> list[Repository]:
        return [
            r for r in self._repositories.values()
            if str(r.project_id) == str(project_id)
        ]

    async def list_all(self) -> list[Repository]:
        return list(self._repositories.values())

    async def get_by_repo_url(self, repo_url: str) -> Repository | None:
        for r in self._repositories.values():
            if r.repo_url == repo_url:
                return r
        return None

    async def delete(self, repository_id: RepositoryId) -> None:
        self._repositories.pop(str(repository_id), None)


class _InMemoryTaskRepo(TaskRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Task] = []

    async def save(self, task: Task) -> None:
        self.saved.append(task)

    async def get_by_id(self, task_id: TaskId) -> Task | None:
        return None

    async def list_by_project(self, project_id: ProjectId, status=None) -> list[Task]:
        return []

    async def delete(self, task_id: TaskId) -> None:
        pass


class _BreakdownProvider(AIProviderPort):
    def __init__(self) -> None:
        self.captured_system_prompts: list[str] = []

    async def generate_stream(
        self, model, system, messages, tools=None, thinking=None, abort_event=None
    ) -> AsyncGenerator[StreamPart, None]:
        self.captured_system_prompts.append(system)

        async def _gen():
            yield StreamPart(type="text_delta", content=BREAKDOWN_JSON)
            yield StreamPart(type="finish", finish_reason="stop")

        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "src" / "api" / "routers").mkdir(parents=True)
    (tmp_path / "src" / "api" / "routers" / "users.py").write_text("# users router")
    return tmp_path


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "skills" / "analyze-with-echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: analyze-with-echo\n"
        "description: Test analysis\n"
        "category: analyze-codebase\n"
        "requires:\n"
        "  bins: [echo]\n"
        "command: [echo, '{prompt}']\n"
        "---\n"
        "\n## Prompt\n\nAnalyze this project.\n"
    )
    return tmp_path / "skills"


@pytest.mark.asyncio
async def test_e2e_analyze_then_breakdown_with_context(
    project_dir: Path, skills_dir: Path
) -> None:
    project = Project.create(name="test-project")
    repository = Repository.create(
        project_id=project.id,
        name="test-project",
        slug="acme/test-project",
        repo_url="https://github.com/acme/test-project",
        path=str(project_dir),
    )

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    analysis_result = await run_repository_analysis(
        AnalysisInput(repository_id=repository.id),
        repository_store,
        skills_dir,
    )

    assert analysis_result.success
    assert analysis_result.context_doc != ""
    assert analysis_result.executor_used == "analyze-with-echo"

    updated_repository = await repository_store.get_by_id(repository.id)
    assert updated_repository is not None
    assert updated_repository.analysis_status == AnalysisStatus.DONE
    assert updated_repository.context_doc is not None

    provider = _BreakdownProvider()
    task_repo = _InMemoryTaskRepo()

    breakdown_result = await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Add email verification",
            story_description="Users should verify email after signup",
            repo_path=str(project_dir),
            project_id=project.id,
            context_doc=updated_repository.context_doc,
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=task_repo,
    )

    assert breakdown_result.success
    assert len(breakdown_result.tasks) == 2
    assert breakdown_result.tasks[0].title == "Add email verification field to User entity"
    assert breakdown_result.tasks[1].title == "Add verification endpoint to users router"

    assert len(provider.captured_system_prompts) > 0
    system_prompt = provider.captured_system_prompts[0]
    assert "Additional Context" in system_prompt
    assert "Analyze this project." in system_prompt or updated_repository.context_doc in system_prompt

    assert len(task_repo.saved) == 2
    assert task_repo.saved[0].project_id == project.id


@pytest.mark.asyncio
async def test_e2e_breakdown_without_analysis_still_works(
    project_dir: Path,
) -> None:
    provider = _BreakdownProvider()
    task_repo = _InMemoryTaskRepo()

    result = await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Add feature",
            story_description="Simple feature",
            repo_path=str(project_dir),
            project_id=ProjectId.generate(),
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=task_repo,
    )

    assert result.success
    assert len(result.tasks) == 2

    system_prompt = provider.captured_system_prompts[0]
    assert "Additional Context" not in system_prompt


@pytest.mark.asyncio
async def test_e2e_analysis_failure_does_not_block_breakdown(
    project_dir: Path, skills_dir: Path
) -> None:
    project = Project.create(name="test-project")
    repository = Repository.create(
        project_id=project.id,
        name="test-project",
        slug="acme/test-project",
        repo_url="https://github.com/acme/test-project",
        path="/nonexistent/path",
    )

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    analysis_result = await run_repository_analysis(
        AnalysisInput(repository_id=repository.id),
        repository_store,
        skills_dir,
    )

    assert not analysis_result.success

    updated = await repository_store.get_by_id(repository.id)
    assert updated is not None
    assert updated.analysis_status == AnalysisStatus.ERROR
    assert updated.context_doc is None

    provider = _BreakdownProvider()
    task_repo = _InMemoryTaskRepo()

    breakdown_result = await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Add feature",
            story_description="Feature desc",
            repo_path=str(project_dir),
            project_id=project.id,
            context_doc=updated.context_doc,
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=task_repo,
    )

    assert breakdown_result.success
    assert "Additional Context" not in provider.captured_system_prompts[0]


@pytest.mark.asyncio
async def test_e2e_context_doc_content_reaches_system_prompt(
    project_dir: Path,
) -> None:
    provider = _BreakdownProvider()
    task_repo = _InMemoryTaskRepo()

    await run_breakdown(
        input=BreakdownInput(
            story_id=StoryId.generate(),
            story_title="Story",
            story_description="Desc",
            repo_path=str(project_dir),
            project_id=ProjectId.generate(),
            context_doc=CONTEXT_DOC,
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        task_repo=task_repo,
    )

    system_prompt = provider.captured_system_prompts[0]
    assert "Python 3.12" in system_prompt
    assert "FastAPI" in system_prompt
    assert "SqlAlchemyUserRepository" in system_prompt
    assert "Clean Architecture" in system_prompt
