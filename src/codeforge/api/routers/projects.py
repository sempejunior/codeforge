from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.project import (
    ProjectConfigSchema,
    ProjectCreateSchema,
    ProjectResponseSchema,
)
from codeforge.domain.entities.project import Project
from codeforge.domain.value_objects.project_id import ProjectId

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> ProjectResponseSchema:
    project = Project.create(
        name=payload.name,
        path=payload.path,
        repo_url=payload.repo_url,
        default_branch=payload.default_branch,
    )
    await repositories.project_repository.save(project)
    return _to_response(project)


@router.get("", response_model=list[ProjectResponseSchema])
async def list_projects(
    path: str | None = Query(default=None),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[ProjectResponseSchema]:
    if path is not None:
        project = await repositories.project_repository.get_by_path(path)
        if project is None:
            return []
        return [_to_response(project)]
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


def _to_response(project: Project) -> ProjectResponseSchema:
    return ProjectResponseSchema(
        id=str(project.id),
        name=project.name,
        path=project.path,
        repo_url=project.repo_url,
        default_branch=project.default_branch,
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
