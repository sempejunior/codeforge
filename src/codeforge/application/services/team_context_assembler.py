from __future__ import annotations

from dataclasses import dataclass

from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.team_id import TeamId
from codeforge.infrastructure.config.workspace import resolve_repository_local_path


@dataclass
class TeamContextRepositorySummary:
    repository_id: RepositoryId
    project_id: ProjectId
    project_name: str
    name: str
    path: str | None
    repo_url: str | None
    source_label: str
    analysis_status: AnalysisStatus
    analysis_executor: str | None
    has_context: bool
    is_selected: bool
    local_path_status: str


@dataclass
class TeamContextSummary:
    team_id: TeamId
    repositories: list[TeamContextRepositorySummary]
    selected_project_ids: list[ProjectId]
    ready_repositories: int
    total_repositories: int
    missing_context_repositories: int
    consolidated_context: str


async def assemble_team_context(
    team_id: TeamId,
    project_repo: ProjectRepositoryPort,
    repository_store: RepositoryStorePort,
    selected_project_ids: list[ProjectId] | None = None,
) -> TeamContextSummary:
    projects = await project_repo.list_by_team(team_id)
    selected = selected_project_ids or [project.id for project in projects]
    selected_set = {str(project_id) for project_id in selected}

    summaries: list[TeamContextRepositorySummary] = []
    context_parts: list[str] = []
    ready_repositories = 0
    missing_context_repositories = 0

    project_names = {project.id: project.name for project in projects}

    for project in projects:
        is_project_selected = str(project.id) in selected_set
        repositories = await repository_store.list_by_project(project.id)

        for repository in repositories:
            has_context = bool(repository.context_doc)
            local_path = resolve_repository_local_path(repository)
            if has_context:
                ready_repositories += 1
            if is_project_selected and not has_context:
                missing_context_repositories += 1
            if is_project_selected and has_context:
                context_parts.append(_render_repository_context(repository, project.name))

            summaries.append(
                TeamContextRepositorySummary(
                    repository_id=repository.id,
                    project_id=project.id,
                    project_name=project.name,
                    name=repository.name,
                    path=local_path,
                    repo_url=repository.repo_url,
                    source_label=_build_source_label(repository, local_path),
                    analysis_status=repository.analysis_status,
                    analysis_executor=repository.analysis_executor,
                    has_context=has_context,
                    is_selected=is_project_selected,
                    local_path_status="resolved" if local_path else "missing",
                )
            )

    return TeamContextSummary(
        team_id=team_id,
        repositories=summaries,
        selected_project_ids=selected,
        ready_repositories=ready_repositories,
        total_repositories=len(summaries),
        missing_context_repositories=missing_context_repositories,
        consolidated_context="\n\n---\n\n".join(context_parts),
    )


def _build_source_label(repository: Repository, local_path: str | None) -> str:
    if repository.repo_url and local_path:
        return "local+repo"
    if repository.repo_url:
        return "repo"
    return "local"


def _render_repository_context(repository: Repository, project_name: str) -> str:
    local_path = resolve_repository_local_path(repository)
    location = repository.repo_url or local_path or "missing-local-repo"
    executor = repository.analysis_executor or "unknown"
    return (
        f"## Repository: {repository.name} (Project: {project_name})\n\n"
        f"- Source: {_build_source_label(repository, local_path)}\n"
        f"- Location: {location}\n"
        f"- Analysis executor: {executor}\n\n"
        f"{repository.context_doc or ''}"
    )
