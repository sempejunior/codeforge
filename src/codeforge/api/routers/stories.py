from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.routers.tasks import task_to_response
from codeforge.api.schemas.story import (
    StoryAddToSprintSchema,
    StoryBreakdownRunSchema,
    StoryCreateSchema,
    StoryResponseSchema,
    StoryUpdateSchema,
)
from codeforge.api.schemas.task import TaskResponseSchema
from codeforge.application.services.workspace_context_assembler import (
    assemble_workspace_context,
)
from codeforge.application.use_cases.run_breakdown import BreakdownInput, run_breakdown
from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.infrastructure.ai.litellm_provider import LiteLLMProvider
from codeforge.infrastructure.config.workspace import resolve_repository_local_path

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.post("", response_model=StoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StoryResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(payload.demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")

    story_project_id = await _validate_story_project(
        payload.project_id,
        demand,
        repositories,
    )
    repository_ids = await _validate_story_repositories(
        payload.repository_ids,
        story_project_id,
        repositories,
    )

    for project_id in payload.linked_projects:
        project = await repositories.project_repository.get_by_id(ProjectId(project_id))
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    story, _ = Story.create(
        demand_id=DemandId(payload.demand_id),
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
        technical_references=payload.technical_references,
        project_id=story_project_id,
        repository_ids=repository_ids,
        linked_projects=[ProjectId(project_id) for project_id in payload.linked_projects],
    )
    await repositories.story_repository.save(story)
    return _to_response(story)


@router.get("", response_model=list[StoryResponseSchema])
async def list_stories(
    demand_id: str | None = Query(default=None),
    sprint_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[StoryResponseSchema]:
    if demand_id is not None:
        try:
            status_value = StoryStatus(status_filter) if status_filter else None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid status: {status_filter}",
            ) from None
        stories = await repositories.story_repository.list_by_demand(
            demand_id=DemandId(demand_id),
            status=status_value,
        )
        return [_to_response(story) for story in stories]

    if sprint_id is not None:
        stories = await repositories.story_repository.list_by_sprint(SprintId(sprint_id))
        return [_to_response(story) for story in stories]

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either demand_id or sprint_id is required",
    )


@router.get("/{story_id}", response_model=StoryResponseSchema)
async def get_story(
    story_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StoryResponseSchema:
    story = await repositories.story_repository.get_by_id(StoryId(story_id))
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return _to_response(story)


@router.patch("/{story_id}", response_model=StoryResponseSchema)
async def update_story(
    story_id: str,
    payload: StoryUpdateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StoryResponseSchema:
    story = await repositories.story_repository.get_by_id(StoryId(story_id))
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    if payload.title is not None:
        story.title = payload.title
    if payload.description is not None:
        story.description = payload.description
    if payload.acceptance_criteria is not None:
        story.acceptance_criteria = payload.acceptance_criteria
    if payload.technical_references is not None:
        story.technical_references = payload.technical_references
    if payload.project_id is not None:
        demand = await repositories.demand_repository.get_by_id(story.demand_id)
        if demand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
        story.project_id = await _validate_story_project(payload.project_id, demand, repositories)
    if payload.repository_ids is not None:
        story.repository_ids = await _validate_story_repositories(
            payload.repository_ids,
            story.project_id,
            repositories,
        )
    if payload.linked_projects is not None:
        for project_id in payload.linked_projects:
            project = await repositories.project_repository.get_by_id(ProjectId(project_id))
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
        story.linked_projects = [ProjectId(project_id) for project_id in payload.linked_projects]
    if payload.status is not None:
        try:
            new_status = StoryStatus(payload.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid status: {payload.status}",
            ) from None
        if story.status != new_status:
            try:
                story.transition_to(new_status)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
    story.updated_at = datetime.now(UTC)
    await repositories.story_repository.save(story)
    return _to_response(story)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story(
    story_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    story = await repositories.story_repository.get_by_id(StoryId(story_id))
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    await repositories.story_repository.delete(story.id)


@router.post("/{story_id}/add-to-sprint", response_model=StoryResponseSchema)
async def add_story_to_sprint(
    story_id: str,
    payload: StoryAddToSprintSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StoryResponseSchema:
    story = await repositories.story_repository.get_by_id(StoryId(story_id))
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    story.add_to_sprint(SprintId(payload.sprint_id))
    await repositories.story_repository.save(story)
    return _to_response(story)


@router.post("/{story_id}/breakdown", response_model=list[TaskResponseSchema])
async def breakdown_story(
    story_id: str,
    payload: StoryBreakdownRunSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[TaskResponseSchema]:
    story = await repositories.story_repository.get_by_id(StoryId(story_id))
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    project_id = ProjectId(payload.project_id)
    project = await repositories.project_repository.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    repo_path: str | None = payload.repo_path
    context_doc: str | None = None

    if payload.repository_id:
        repository = await repositories.repository_store.get_by_id(
            RepositoryId(payload.repository_id)
        )
        if repository is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        if repo_path is None:
            repo_path = resolve_repository_local_path(repository)
        context_doc = repository.context_doc
    else:
        project_repos = await repositories.repository_store.list_by_project(project_id)
        if project_repos:
            first_repo = project_repos[0]
            if repo_path is None:
                repo_path = resolve_repository_local_path(first_repo)
            context_doc = first_repo.context_doc

    if repo_path is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Repositorio local nao encontrado. Configure a pasta base do workspace.",
        )

    workspace_context_md: str | None = None
    demand = await repositories.demand_repository.get_by_id(story.demand_id)
    if demand is not None and demand.team_id is not None:
        workspace = await assemble_workspace_context(
            team_id=demand.team_id,
            project_repo=repositories.project_repository,
            repository_store=repositories.repository_store,
            team_document_repo=repositories.team_document_repository,
            demand_id=demand.id,
            demand_repo=repositories.demand_repository,
        )
        if workspace.consolidated_markdown:
            workspace_context_md = workspace.consolidated_markdown

    result = await run_breakdown(
        input=BreakdownInput(
            story_id=story.id,
            story_title=story.title,
            story_description=story.description,
            repo_path=repo_path,
            project_id=project_id,
            context_doc=context_doc,
            workspace_context=workspace_context_md,
        ),
        provider=LiteLLMProvider(),
        model=ModelId(project.config.default_model),
        task_repo=repositories.task_repository,
    )
    if not result.success:
        detail = result.raw_output[:300] if result.raw_output else "Breakdown agent failed"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)
    return [task_to_response(task) for task in result.tasks]


def _to_response(story: Story) -> StoryResponseSchema:
    return StoryResponseSchema(
        id=str(story.id),
        demand_id=str(story.demand_id),
        project_id=str(story.project_id) if story.project_id else None,
        repository_ids=[str(repository_id) for repository_id in story.repository_ids],
        title=story.title,
        description=story.description,
        acceptance_criteria=list(story.acceptance_criteria),
        technical_references=list(story.technical_references),
        linked_projects=[str(project_id) for project_id in story.linked_projects],
        sprint_id=str(story.sprint_id) if story.sprint_id else None,
        status=story.status.value,
        created_at=story.created_at,
        updated_at=story.updated_at,
    )


async def _validate_story_project(
    project_id: str | None,
    demand,
    repositories: RepositoryContainer,
) -> ProjectId | None:
    if project_id is None:
        return None
    typed_project_id = ProjectId(project_id)
    if all(
        linked_project.project_id != typed_project_id
        for linked_project in demand.linked_projects
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Story project must be linked to the demand",
        )
    project = await repositories.project_repository.get_by_id(typed_project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return typed_project_id


async def _validate_story_repositories(
    repository_ids: list[str],
    project_id: ProjectId | None,
    repositories: RepositoryContainer,
) -> list[RepositoryId]:
    if not repository_ids:
        return []
    if project_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Story repositories require a target project",
        )
    project_repositories = await repositories.repository_store.list_by_project(project_id)
    available_repository_ids = {repository.id for repository in project_repositories}
    typed_repository_ids = [RepositoryId(repository_id) for repository_id in repository_ids]
    if any(repository_id not in available_repository_ids for repository_id in typed_repository_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Repository not linked to the selected project",
        )
    return typed_repository_ids
