from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.project import (
    ProjectConfigSchema,
    ProjectCreateSchema,
    ProjectResponseSchema,
    ProjectUpdateSchema,
)
from codeforge.domain.entities.project import CodeReviewMode, Project
from codeforge.domain.entities.team_document import TeamDocument, TeamDocumentSource
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_id import TeamId

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> ProjectResponseSchema:
    if payload.team_id is not None:
        team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    project = Project.create(
        name=payload.name,
        team_id=TeamId(payload.team_id) if payload.team_id else None,
    )
    await repositories.project_repository.save(project)

    if project.team_id is not None:
        existing_folder = await repositories.team_document_repository.find_folder_for_project(
            project.team_id, project.id
        )
        if existing_folder is None:
            folder = TeamDocument.create_folder(
                team_id=project.team_id,
                title=project.name,
                source=TeamDocumentSource.SYSTEM,
                linked_project_id=project.id,
            )
            await repositories.team_document_repository.save(folder)

    return _to_response(project)


@router.get("", response_model=list[ProjectResponseSchema])
async def list_projects(
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[ProjectResponseSchema]:
    projects = await repositories.project_repository.list_all()
    return [_to_response(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponseSchema)
async def get_project(
    project_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> ProjectResponseSchema:
    project = await repositories.project_repository.get_by_id(ProjectId(project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponseSchema)
async def update_project(
    project_id: str,
    payload: ProjectUpdateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> ProjectResponseSchema:
    project = await repositories.project_repository.get_by_id(ProjectId(project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if payload.name is not None:
        project.name = payload.name
    if payload.team_id is not None:
        team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        project.team_id = TeamId(payload.team_id)
    if payload.config is not None:
        cfg = payload.config
        if cfg.max_parallel_subtasks is not None:
            project.config.max_parallel_subtasks = cfg.max_parallel_subtasks
        if cfg.max_qa_cycles is not None:
            project.config.max_qa_cycles = cfg.max_qa_cycles
        if cfg.max_subtask_retries is not None:
            project.config.max_subtask_retries = cfg.max_subtask_retries
        if cfg.auto_continue_delay_seconds is not None:
            project.config.auto_continue_delay_seconds = cfg.auto_continue_delay_seconds
        if cfg.default_model is not None:
            project.config.default_model = cfg.default_model
        if cfg.code_review_mode is not None:
            project.config.code_review_mode = CodeReviewMode(cfg.code_review_mode)
        if cfg.human_review_required is not None:
            project.config.human_review_required = cfg.human_review_required
        if cfg.auto_start_tasks is not None:
            project.config.auto_start_tasks = cfg.auto_start_tasks
        if cfg.breakdown_requires_approval is not None:
            project.config.breakdown_requires_approval = cfg.breakdown_requires_approval
        if cfg.auto_merge is not None:
            project.config.auto_merge = cfg.auto_merge
    project.updated_at = datetime.now(UTC)
    await repositories.project_repository.save(project)

    if project.team_id is not None:
        existing_folder = await repositories.team_document_repository.find_folder_for_project(
            project.team_id, project.id
        )
        if existing_folder is None:
            folder = TeamDocument.create_folder(
                team_id=project.team_id,
                title=project.name,
                source=TeamDocumentSource.SYSTEM,
                linked_project_id=project.id,
            )
            await repositories.team_document_repository.save(folder)
        elif payload.name is not None and existing_folder.title != project.name:
            existing_folder.title = project.name
            existing_folder.updated_at = datetime.now(UTC)
            await repositories.team_document_repository.save(existing_folder)

    return _to_response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    typed_project_id = ProjectId(project_id)
    project = await repositories.project_repository.get_by_id(typed_project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    demands = await repositories.demand_repository.list_all()
    for demand in demands:
        if demand.status.value in {"done", "cancelled"}:
            continue
        if any(
            linked_project.project_id == typed_project_id
            for linked_project in demand.linked_projects
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project linked to active demands cannot be deleted",
            )

    documents = await repositories.team_document_repository.list_by_project(typed_project_id)
    for document in reversed(documents):
        await repositories.team_document_repository.delete(document.id)
    await repositories.project_repository.delete(typed_project_id)


def _to_response(project: Project) -> ProjectResponseSchema:
    return ProjectResponseSchema(
        id=str(project.id),
        name=project.name,
        team_id=str(project.team_id) if project.team_id else None,
        config=ProjectConfigSchema(
            max_parallel_subtasks=project.config.max_parallel_subtasks,
            max_qa_cycles=project.config.max_qa_cycles,
            max_subtask_retries=project.config.max_subtask_retries,
            auto_continue_delay_seconds=project.config.auto_continue_delay_seconds,
            default_model=project.config.default_model,
            code_review_mode=project.config.code_review_mode.value,
            human_review_required=project.config.human_review_required,
            auto_start_tasks=project.config.auto_start_tasks,
            breakdown_requires_approval=project.config.breakdown_requires_approval,
            auto_merge=project.config.auto_merge,
        ),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )
