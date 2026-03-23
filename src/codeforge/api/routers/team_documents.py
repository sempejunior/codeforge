from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.team_document import (
    TeamDocumentCreateSchema,
    TeamDocumentResponseSchema,
    TeamDocumentUpdateSchema,
    TeamWorkspaceResponseSchema,
)
from codeforge.domain.entities.team_document import (
    TeamDocument,
    TeamDocumentKind,
    TeamDocumentSource,
)
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.team_document_id import TeamDocumentId
from codeforge.domain.value_objects.team_id import TeamId

router = APIRouter(prefix="/api/team-documents", tags=["team-documents"])


def _to_response(document: TeamDocument) -> TeamDocumentResponseSchema:
    return TeamDocumentResponseSchema(
        id=str(document.id),
        team_id=str(document.team_id),
        title=document.title,
        kind=document.kind.value,
        parent_id=str(document.parent_id) if document.parent_id else None,
        content=document.content,
        linked_project_id=str(document.linked_project_id) if document.linked_project_id else None,
        linked_repository_id=str(document.linked_repository_id) if document.linked_repository_id else None,
        source=document.source.value,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def _reconcile_workspace_folders(
    team_id: TeamId,
    repos: RepositoryContainer,
) -> None:
    projects = await repos.project_repository.list_by_team(team_id)
    if not projects:
        return

    for project in projects:
        project_folder = await repos.team_document_repository.find_folder_for_project(
            team_id, project.id
        )
        if project_folder is None:
            project_folder = TeamDocument.create_folder(
                team_id=team_id,
                title=project.name,
                source=TeamDocumentSource.SYSTEM,
                linked_project_id=project.id,
            )
            await repos.team_document_repository.save(project_folder)

        repositories = await repos.repository_store.list_by_project(project.id)
        for repository in repositories:
            repo_folder = await repos.team_document_repository.find_folder_for_repository(
                team_id, repository.id
            )
            if repo_folder is None:
                repo_folder = TeamDocument.create_folder(
                    team_id=team_id,
                    title=repository.name,
                    parent_id=project_folder.id,
                    source=TeamDocumentSource.SYSTEM,
                    linked_repository_id=repository.id,
                )
                await repos.team_document_repository.save(repo_folder)


@router.post("", response_model=TeamDocumentResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_team_document(
    payload: TeamDocumentCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamDocumentResponseSchema:
    team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    if payload.parent_id is not None:
        parent = await repositories.team_document_repository.get_by_id(
            TeamDocumentId(payload.parent_id)
        )
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent document not found",
            )

    source = TeamDocumentSource(payload.source)
    linked_project_id = ProjectId(payload.linked_project_id) if payload.linked_project_id else None
    linked_repository_id = (
        RepositoryId(payload.linked_repository_id) if payload.linked_repository_id else None
    )
    if payload.kind == TeamDocumentKind.FOLDER.value:
        document = TeamDocument.create_folder(
            team_id=TeamId(payload.team_id),
            title=payload.title,
            parent_id=TeamDocumentId(payload.parent_id) if payload.parent_id else None,
            source=source,
            linked_project_id=linked_project_id,
            linked_repository_id=linked_repository_id,
        )
    else:
        document = TeamDocument.create_document(
            team_id=TeamId(payload.team_id),
            title=payload.title,
            content=payload.content,
            parent_id=TeamDocumentId(payload.parent_id) if payload.parent_id else None,
            source=source,
            linked_project_id=linked_project_id,
            linked_repository_id=linked_repository_id,
        )

    await repositories.team_document_repository.save(document)
    return _to_response(document)


@router.get("/team/{team_id}", response_model=TeamWorkspaceResponseSchema)
async def list_team_documents(
    team_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamWorkspaceResponseSchema:
    tid = TeamId(team_id)
    team = await repositories.team_repository.get_by_id(tid)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    await _reconcile_workspace_folders(tid, repositories)

    documents = await repositories.team_document_repository.list_by_team(tid)
    return TeamWorkspaceResponseSchema(
        team_id=team_id,
        documents=[_to_response(document) for document in documents],
    )


@router.patch("/{document_id}", response_model=TeamDocumentResponseSchema)
async def update_team_document(
    document_id: str,
    payload: TeamDocumentUpdateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamDocumentResponseSchema:
    document = await repositories.team_document_repository.get_by_id(TeamDocumentId(document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if payload.title is not None:
        document.title = payload.title
    if payload.content is not None:
        document.content = payload.content
    if payload.parent_id is not None:
        document.parent_id = TeamDocumentId(payload.parent_id)
    document.updated_at = datetime.now(UTC)

    await repositories.team_document_repository.save(document)
    return _to_response(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team_document(
    document_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    document = await repositories.team_document_repository.get_by_id(TeamDocumentId(document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await repositories.team_document_repository.delete(TeamDocumentId(document_id))
