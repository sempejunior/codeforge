from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.application.services.team_context_assembler import assemble_team_context
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.team_id import TeamId


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


@pytest.mark.asyncio
async def test_assemble_team_context_reports_readiness(tmp_path: Path) -> None:
    team_id = TeamId.generate()

    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / ".git").mkdir()

    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / ".git").mkdir()

    ready_project = Project.create(name="api", team_id=team_id)
    ready_repo = Repository.create(
        project_id=ready_project.id,
        name="api-backend",
        slug="acme/api",
        repo_url="https://github.com/acme/api",
        path=str(api_dir),
    )
    ready_repo.analysis_status = AnalysisStatus.DONE
    ready_repo.analysis_executor = "analyze-with-claude"
    ready_repo.context_doc = "# API context"

    missing_project = Project.create(name="web", team_id=team_id)
    missing_repo = Repository.create(
        project_id=missing_project.id,
        name="web-frontend",
        slug="acme/web",
        repo_url="https://github.com/acme/web",
        path=str(web_dir),
    )
    missing_repo.analysis_status = AnalysisStatus.NONE

    project_repo = _InMemoryProjectRepo()
    await project_repo.save(ready_project)
    await project_repo.save(missing_project)

    repository_store = _InMemoryRepositoryStore()
    await repository_store.save(ready_repo)
    await repository_store.save(missing_repo)

    summary = await assemble_team_context(
        team_id=team_id,
        project_repo=project_repo,
        repository_store=repository_store,
        selected_project_ids=[ready_project.id, missing_project.id],
    )

    assert summary.ready_repositories == 1
    assert summary.total_repositories == 2
    assert summary.missing_context_repositories == 1
    assert "Analysis executor: analyze-with-claude" in summary.consolidated_context
    assert any(repo.source_label == "local+repo" for repo in summary.repositories)
