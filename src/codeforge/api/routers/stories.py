from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.story import (
    StoryAddToSprintSchema,
    StoryCreateSchema,
    StoryResponseSchema,
)
from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId

router = APIRouter(prefix="/api/stories", tags=["stories"])


@router.post("", response_model=StoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StoryResponseSchema:
    story, _ = Story.create(
        demand_id=DemandId(payload.demand_id),
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
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
        status_value = StoryStatus(status_filter) if status_filter else None
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


def _to_response(story: Story) -> StoryResponseSchema:
    return StoryResponseSchema(
        id=str(story.id),
        demand_id=str(story.demand_id),
        title=story.title,
        description=story.description,
        acceptance_criteria=list(story.acceptance_criteria),
        sprint_id=str(story.sprint_id) if story.sprint_id else None,
        status=story.status.value,
        created_at=story.created_at,
        updated_at=story.updated_at,
    )
