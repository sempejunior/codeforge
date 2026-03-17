from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.sprint import (
    SprintCreateSchema,
    SprintMetricsSchema,
    SprintResponseSchema,
)
from codeforge.domain.entities.sprint import Sprint, SprintStatus
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


@router.post("", response_model=SprintResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_sprint(
    payload: SprintCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> SprintResponseSchema:
    sprint, _ = Sprint.create(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        story_ids=[StoryId(story_id) for story_id in payload.story_ids],
    )
    await repositories.sprint_repository.save(sprint)
    return _to_response(sprint)


@router.get("", response_model=list[SprintResponseSchema])
async def list_sprints(
    status_filter: str | None = Query(default=None, alias="status"),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[SprintResponseSchema]:
    status_value = SprintStatus(status_filter) if status_filter else None
    sprints = await repositories.sprint_repository.list_all(status=status_value)
    return [_to_response(sprint) for sprint in sprints]


@router.get("/{sprint_id}", response_model=SprintResponseSchema)
async def get_sprint(
    sprint_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> SprintResponseSchema:
    sprint = await repositories.sprint_repository.get_by_id(SprintId(sprint_id))
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    return _to_response(sprint)


@router.get("/active/current", response_model=SprintResponseSchema | None)
async def get_active_sprint(
    repositories: RepositoryContainer = Depends(get_repositories),
) -> SprintResponseSchema | None:
    sprint = await repositories.sprint_repository.get_active()
    if sprint is None:
        return None
    return _to_response(sprint)


@router.post("/{sprint_id}/start", response_model=SprintResponseSchema)
async def start_sprint(
    sprint_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> SprintResponseSchema:
    sprint = await repositories.sprint_repository.get_by_id(SprintId(sprint_id))
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    sprint.start()
    await repositories.sprint_repository.save(sprint)
    return _to_response(sprint)


@router.post("/{sprint_id}/complete", response_model=SprintResponseSchema)
async def complete_sprint(
    sprint_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> SprintResponseSchema:
    sprint = await repositories.sprint_repository.get_by_id(SprintId(sprint_id))
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    sprint.complete()
    await repositories.sprint_repository.save(sprint)
    return _to_response(sprint)


def _to_response(sprint: Sprint) -> SprintResponseSchema:
    return SprintResponseSchema(
        id=str(sprint.id),
        name=sprint.name,
        start_date=sprint.start_date,
        end_date=sprint.end_date,
        story_ids=[str(story_id) for story_id in sprint.story_ids],
        status=sprint.status.value,
        metrics=SprintMetricsSchema(
            tasks_done=sprint.metrics.tasks_done,
            tasks_total=sprint.metrics.tasks_total,
            stories_done=sprint.metrics.stories_done,
            stories_total=sprint.metrics.stories_total,
            completion_pct=sprint.metrics.completion_pct,
        ),
        created_at=sprint.created_at,
        updated_at=sprint.updated_at,
    )
