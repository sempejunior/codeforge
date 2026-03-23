from __future__ import annotations

from dataclasses import dataclass, field

from codeforge.domain.entities.team_document import TeamDocumentKind, TeamDocumentSource
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.team_document_repository import TeamDocumentRepositoryPort
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_document_id import TeamDocumentId
from codeforge.domain.value_objects.team_id import TeamId

_WORKSPACE_FOLDERS = frozenset({"Produto", "Arquitetura", "Decisoes"})


@dataclass
class WorkspaceContext:
    consolidated_markdown: str
    documents_used: list[str] = field(default_factory=list)
    projects_with_context: int = 0
    projects_without_context: int = 0


async def assemble_workspace_context(
    team_id: TeamId,
    project_repo: ProjectRepositoryPort,
    repository_store: RepositoryStorePort,
    team_document_repo: TeamDocumentRepositoryPort,
    demand_id: DemandId | None = None,
    demand_repo: DemandRepositoryPort | None = None,
    selected_project_ids: list[ProjectId] | None = None,
    selected_document_ids: list[str] | None = None,
) -> WorkspaceContext:
    documents = await team_document_repo.list_by_team(team_id)
    allowed_document_ids = set(selected_document_ids or [])

    folder_titles: dict[str, str] = {}
    for doc in documents:
        if doc.kind == TeamDocumentKind.FOLDER:
            folder_titles[str(doc.id)] = doc.title

    parts: list[str] = []
    documents_used: list[str] = []

    for doc in documents:
        if doc.kind != TeamDocumentKind.DOCUMENT or not doc.content:
            continue
        if not _is_relevant_document(doc.parent_id, doc.source, folder_titles):
            continue
        if allowed_document_ids and str(doc.id) not in allowed_document_ids:
            continue

        parent_title = folder_titles.get(str(doc.parent_id), "") if doc.parent_id else ""
        header = f"{parent_title} / {doc.title}" if parent_title else doc.title
        parts.append(f"## {header}\n\n{doc.content}")
        documents_used.append(doc.title)

    projects_with_context = 0
    projects_without_context = 0

    linked_project_ids: set[ProjectId] = set()
    if demand_id is not None and demand_repo is not None:
        demand = await demand_repo.get_by_id(demand_id)
        if demand is not None:
            linked_project_ids = {
                lp.project_id for lp in demand.linked_projects
            }
    if selected_project_ids is not None:
        linked_project_ids &= set(selected_project_ids)

    if linked_project_ids:
        for project_id in linked_project_ids:
            project = await project_repo.get_by_id(project_id)
            if project is None:
                continue
            repositories = await repository_store.list_by_project(project_id)
            project_has_any_context = False
            for repo in repositories:
                if repo.context_doc:
                    project_has_any_context = True
                    parts.append(
                        f"## Repository: {repo.name} (Project: {project.name})\n\n{repo.context_doc}"
                    )
            if project_has_any_context:
                projects_with_context += 1
            else:
                projects_without_context += 1

    return WorkspaceContext(
        consolidated_markdown="\n\n---\n\n".join(parts),
        documents_used=documents_used,
        projects_with_context=projects_with_context,
        projects_without_context=projects_without_context,
    )


def _is_relevant_document(
    parent_id: TeamDocumentId | None,
    source: TeamDocumentSource,
    folder_titles: dict[str, str],
) -> bool:
    if source == TeamDocumentSource.GENERATED:
        return True
    if parent_id is None:
        return False
    parent_title = folder_titles.get(str(parent_id), "")
    return parent_title in _WORKSPACE_FOLDERS
