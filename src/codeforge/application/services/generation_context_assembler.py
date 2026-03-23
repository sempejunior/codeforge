from __future__ import annotations

from dataclasses import dataclass, field

from codeforge.domain.entities.team_document import (
    TeamDocument,
    TeamDocumentKind,
    TeamDocumentSource,
)
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.team_document_repository import TeamDocumentRepositoryPort
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_id import TeamId

_WORKSPACE_FOLDERS = frozenset({"Produto", "Arquitetura", "Decisoes"})


@dataclass
class GenerationContextItem:
    id: str
    kind: str
    title: str
    preview: str
    selected: bool
    source: str


@dataclass
class GenerationContextSummary:
    team_id: TeamId
    demand_id: DemandId
    selected_project_ids: list[ProjectId] = field(default_factory=list)
    selected_document_ids: list[str] = field(default_factory=list)
    projects_with_context: int = 0
    projects_without_context: int = 0
    items: list[GenerationContextItem] = field(default_factory=list)


async def assemble_generation_context(
    team_id: TeamId,
    demand_id: DemandId,
    project_repo: ProjectRepositoryPort,
    repository_store: RepositoryStorePort,
    team_document_repo: TeamDocumentRepositoryPort,
    demand_repo: DemandRepositoryPort,
    selected_project_ids: list[ProjectId] | None = None,
    selected_document_ids: list[str] | None = None,
) -> GenerationContextSummary:
    demand = await demand_repo.get_by_id(demand_id)
    if demand is None:
        raise ValueError(f"Demand {demand_id} not found")

    linked_project_ids = [linked_project.project_id for linked_project in demand.linked_projects]
    allowed_project_ids = set(selected_project_ids or linked_project_ids)
    allowed_document_ids = set(selected_document_ids or [])

    items: list[GenerationContextItem] = []
    projects_with_context = 0
    projects_without_context = 0
    selected_project_id_values: list[ProjectId] = []

    for project_id in linked_project_ids:
        project = await project_repo.get_by_id(project_id)
        if project is None:
            continue
        selected = project_id in allowed_project_ids
        if selected:
            selected_project_id_values.append(project_id)

        repositories = await repository_store.list_by_project(project_id)
        project_has_context = any(repo.context_doc for repo in repositories)

        if project_has_context:
            projects_with_context += 1
        else:
            projects_without_context += 1

        context_preview = ""
        for repo in repositories:
            if repo.context_doc:
                context_preview += repo.context_doc + "\n"
        if not context_preview:
            context_preview = "Projeto sem analise disponivel ainda."

        items.append(
            GenerationContextItem(
                id=f"project:{project.id}",
                kind="project_context",
                title=project.name,
                preview=_truncate(context_preview),
                selected=selected,
                source="generated" if project_has_context else "missing",
            )
        )

    documents = await team_document_repo.list_by_team(team_id)
    folder_titles = {
        str(document.id): document.title
        for document in documents
        if document.kind == TeamDocumentKind.FOLDER
    }

    selected_document_id_values: list[str] = []
    for document in documents:
        if not _is_relevant_document(document, folder_titles):
            continue
        selected = not allowed_document_ids or str(document.id) in allowed_document_ids
        if selected:
            selected_document_id_values.append(str(document.id))
        parent_title = folder_titles.get(str(document.parent_id), "") if document.parent_id else ""
        title = f"{parent_title} / {document.title}" if parent_title else document.title
        items.append(
            GenerationContextItem(
                id=str(document.id),
                kind="workspace_document",
                title=title,
                preview=_truncate(document.content),
                selected=selected,
                source=document.source.value,
            )
        )

    return GenerationContextSummary(
        team_id=team_id,
        demand_id=demand_id,
        selected_project_ids=selected_project_id_values,
        selected_document_ids=selected_document_id_values,
        projects_with_context=projects_with_context,
        projects_without_context=projects_without_context,
        items=items,
    )


def _is_relevant_document(
    document: TeamDocument,
    folder_titles: dict[str, str],
) -> bool:
    if document.kind != TeamDocumentKind.DOCUMENT or not document.content:
        return False
    if document.source == TeamDocumentSource.GENERATED:
        return True
    if document.parent_id is None:
        return False
    parent_title = folder_titles.get(str(document.parent_id), "")
    return parent_title in _WORKSPACE_FOLDERS


def _truncate(content: str, limit: int = 220) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."
