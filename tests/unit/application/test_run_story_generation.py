from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from codeforge.application.use_cases.run_story_generation import (
    GenerationEvent,
    GenerationInput,
    run_story_generation,
)
from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.entities.demand import Demand, GenerationStatus, LinkedProject
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.entities.story import Story
from codeforge.domain.ports.ai_provider import (
    AIProviderPort,
    GenerateResult,
    Message,
    StreamPart,
)
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.team_id import TeamId

GENERATION_JSON = """\
{
  "stories": [
    {
      "title": "Implement PIX payment endpoint",
      "description": "Create POST /api/payments/pix endpoint",
      "acceptance_criteria": ["Endpoint returns 201", "QR code generated"],
      "technical_references": ["src/api/routers/payments.py", "PaymentService"]
    },
    {
      "title": "Add payment confirmation webhook",
      "description": "Handle BCB webhook for payment confirmation",
      "acceptance_criteria": ["POST /api/webhooks/pix processes callback"],
      "technical_references": ["src/api/routers/webhooks.py", "WebhookHandler"]
    }
  ]
}
"""


class _MockProvider(AIProviderPort):
    def __init__(self, content: str) -> None:
        self._content = content
        self.captured_system_prompts: list[str] = []
        self.captured_messages: list[list[Message]] = []

    async def generate_stream(
        self, model, system, messages, tools=None, thinking=None, abort_event=None
    ) -> AsyncGenerator[StreamPart, None]:
        self.captured_system_prompts.append(system)
        self.captured_messages.append(messages)

        async def _gen():
            yield StreamPart(type="text_delta", content=self._content)
            yield StreamPart(type="finish", finish_reason="stop")

        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")


class _InMemoryDemandRepo(DemandRepositoryPort):
    def __init__(self) -> None:
        self._demands: dict[str, Demand] = {}

    async def save(self, demand: Demand) -> None:
        self._demands[str(demand.id)] = demand

    async def get_by_id(self, demand_id: DemandId | str) -> Demand | None:
        return self._demands.get(str(demand_id))

    async def list_all(self, status=None) -> list[Demand]:
        return list(self._demands.values())

    async def delete(self, demand_id: DemandId) -> None:
        self._demands.pop(str(demand_id), None)


class _InMemoryProjectRepo(ProjectRepositoryPort):
    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}

    async def save(self, project: Project) -> None:
        self._projects[str(project.id)] = project

    async def get_by_id(self, project_id: ProjectId) -> Project | None:
        return self._projects.get(str(project_id))

    async def list_all(self) -> list[Project]:
        return list(self._projects.values())

    async def list_by_team(self, team_id: TeamId) -> list[Project]:
        return [project for project in self._projects.values() if project.team_id == team_id]

    async def delete(self, project_id: ProjectId) -> None:
        self._projects.pop(str(project_id), None)


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


class _InMemoryStoryRepo(StoryRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Story] = []

    async def save(self, story: Story) -> None:
        self.saved.append(story)

    async def get_by_id(self, story_id: StoryId) -> Story | None:
        return None

    async def list_by_demand(self, demand_id: DemandId, status=None) -> list[Story]:
        return [s for s in self.saved if s.demand_id == demand_id]

    async def list_by_sprint(self, sprint_id: SprintId) -> list[Story]:
        return []

    async def delete(self, story_id: StoryId) -> None:
        pass


def _make_project_and_repository(
    name: str = "test-project",
    path: str = "/tmp/test",
) -> tuple[Project, Repository]:
    project = Project.create(name=name)
    repository = Repository.create(
        project_id=project.id,
        name=name,
        slug=f"acme/{name}",
        repo_url=f"https://github.com/acme/{name}",
        path=path,
    )
    repository.analysis_status = AnalysisStatus.DONE
    repository.context_doc = "# Test Project\n\nThis is a test project with FastAPI."
    return project, repository


def _make_demand(project_id: ProjectId) -> tuple[Demand, list]:
    return Demand.create(
        title="Implement PIX checkout",
        business_objective="Allow customers to pay with PIX",
        acceptance_criteria=["PIX QR code generated", "Payment confirmed"],
        linked_projects=[LinkedProject(project_id=project_id)],
    )


@pytest.mark.asyncio
async def test_happy_path_generates_stories() -> None:
    project, repository = _make_project_and_repository()
    demand, _ = _make_demand(project.id)

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    story_repo = _InMemoryStoryRepo()
    provider = _MockProvider(GENERATION_JSON)

    events: list[GenerationEvent] = []

    result = await run_story_generation(
        input=GenerationInput(demand_id=str(demand.id), skills_dir=Path("/tmp")),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=story_repo,
        provider=provider,
        on_event=events.append,
    )

    assert len(result) == 2
    assert result[0].title == "Implement PIX payment endpoint"
    assert result[1].title == "Add payment confirmation webhook"
    assert result[0].technical_references == ["src/api/routers/payments.py", "PaymentService"]
    assert result[0].project_id == project.id
    assert len(story_repo.saved) == 2

    updated_demand = await demand_repo.get_by_id(demand.id)
    assert updated_demand is not None
    assert updated_demand.generation_status == GenerationStatus.DONE
    assert updated_demand.generation_error is None

    assert any(e.stage == "analyzing_projects" for e in events)
    assert any(e.stage == "generating_stories" for e in events)
    assert any(e.done for e in events)


@pytest.mark.asyncio
async def test_context_doc_injected_into_system_prompt() -> None:
    project, repository = _make_project_and_repository()
    demand, _ = _make_demand(project.id)

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    provider = _MockProvider(GENERATION_JSON)

    await run_story_generation(
        input=GenerationInput(demand_id=str(demand.id), skills_dir=Path("/tmp")),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=_InMemoryStoryRepo(),
        provider=provider,
    )

    assert len(provider.captured_system_prompts) > 0
    system_prompt = provider.captured_system_prompts[0]
    assert "test-project" in system_prompt
    assert "FastAPI" in system_prompt
    assert "technical_references" in provider.captured_messages[0][0].content


@pytest.mark.asyncio
async def test_generation_failure_sets_error_status() -> None:
    project, repository = _make_project_and_repository()
    demand, _ = _make_demand(project.id)

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    provider = _MockProvider("not valid json at all")
    events: list[GenerationEvent] = []

    result = await run_story_generation(
        input=GenerationInput(demand_id=str(demand.id), skills_dir=Path("/tmp")),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=_InMemoryStoryRepo(),
        provider=provider,
        on_event=events.append,
    )

    assert len(result) == 0

    updated_demand = await demand_repo.get_by_id(demand.id)
    assert updated_demand is not None
    assert updated_demand.generation_status == GenerationStatus.ERROR
    assert updated_demand.generation_error is not None

    assert any(e.error for e in events)


@pytest.mark.asyncio
async def test_demand_not_found_raises() -> None:
    demand_repo = _InMemoryDemandRepo()
    project_repo = _InMemoryProjectRepo()
    repository_store = _InMemoryRepositoryStore()
    story_repo = _InMemoryStoryRepo()
    provider = _MockProvider("{}")

    with pytest.raises(ValueError, match="not found"):
        await run_story_generation(
            input=GenerationInput(
                demand_id=str(uuid.uuid4()), skills_dir=Path("/tmp")
            ),
            demand_repo=demand_repo,
            project_repo=project_repo,
            repository_store=repository_store,
            story_repo=story_repo,
            provider=provider,
        )


@pytest.mark.asyncio
async def test_multiple_projects_context_merged() -> None:
    project1, repo1 = _make_project_and_repository(name="backend", path="/tmp/backend")
    repo1.context_doc = "# Backend\nFastAPI + SQLAlchemy"

    project2, repo2 = _make_project_and_repository(name="frontend", path="/tmp/frontend")
    repo2.context_doc = "# Frontend\nReact 19 + Tailwind"

    demand, _ = Demand.create(
        title="Cross-repo feature",
        business_objective="Feature spanning both repos",
        linked_projects=[
            LinkedProject(project_id=project1.id),
            LinkedProject(project_id=project2.id),
        ],
    )

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project1)
    await project_repo.save(project2)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repo1)
    await repository_store.save(repo2)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    provider = _MockProvider(GENERATION_JSON)

    await run_story_generation(
        input=GenerationInput(demand_id=str(demand.id), skills_dir=Path("/tmp")),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=_InMemoryStoryRepo(),
        provider=provider,
    )

    system_prompt = provider.captured_system_prompts[0]
    assert "backend" in system_prompt.lower()
    assert "frontend" in system_prompt.lower()
    assert "FastAPI" in system_prompt
    assert "React 19" in system_prompt


@pytest.mark.asyncio
async def test_selected_project_ids_limit_generation_context() -> None:
    team_id = TeamId.generate()
    project1, repo1 = _make_project_and_repository(name="backend", path="/tmp/backend")
    project1.team_id = team_id
    repo1.context_doc = "# Backend\nFastAPI"

    project2, repo2 = _make_project_and_repository(name="frontend", path="/tmp/frontend")
    project2.team_id = team_id
    repo2.context_doc = "# Frontend\nReact 19"

    demand, _ = Demand.create(
        title="Cross-repo feature",
        business_objective="Feature spanning both repos",
        team_id=team_id,
        linked_projects=[
            LinkedProject(project_id=project1.id),
            LinkedProject(project_id=project2.id),
        ],
    )

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project1)
    await project_repo.save(project2)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repo1)
    await repository_store.save(repo2)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    provider = _MockProvider(GENERATION_JSON)

    await run_story_generation(
        input=GenerationInput(
            demand_id=str(demand.id),
            skills_dir=Path("/tmp"),
            selected_project_ids=[str(project1.id)],
        ),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=_InMemoryStoryRepo(),
        provider=provider,
    )

    system_prompt = provider.captured_system_prompts[0]
    assert "backend" in system_prompt.lower()
    assert "fastapi" in system_prompt.lower()
    assert "frontend" not in system_prompt.lower()


@pytest.mark.asyncio
async def test_repository_without_context_triggers_analysis(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "skills" / "analyze-with-echo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: analyze-with-echo\n"
        "description: Test analysis\n"
        "category: analyze-codebase\n"
        "requires:\n"
        "  bins: [echo]\n"
        "command: [echo, 'analyzed output']\n"
        "---\n"
        "\n## Prompt\n\nAnalyze.\n"
    )

    (tmp_path / ".git").mkdir()
    project = Project.create(name="unanalyzed")
    repository = Repository.create(
        project_id=project.id,
        name="unanalyzed",
        slug="acme/unanalyzed",
        repo_url="https://github.com/acme/unanalyzed",
        path=str(tmp_path),
    )

    demand, _ = Demand.create(
        title="Feature",
        business_objective="Objective",
        linked_projects=[LinkedProject(project_id=project.id)],
    )

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(project)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(repository)

    demand_repo = _InMemoryDemandRepo()
    await demand_repo.save(demand)

    provider = _MockProvider(GENERATION_JSON)

    result = await run_story_generation(
        input=GenerationInput(
            demand_id=str(demand.id),
            skills_dir=tmp_path / "skills",
        ),
        demand_repo=demand_repo,
        project_repo=project_repo,
        repository_store=repository_store,
        story_repo=_InMemoryStoryRepo(),
        provider=provider,
    )

    assert len(result) == 2

    updated_repository = await repository_store.get_by_id(repository.id)
    assert updated_repository is not None
    assert updated_repository.analysis_status == AnalysisStatus.DONE
    assert updated_repository.context_doc is not None
