from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.demand import (
    DemandAssistantStorySchema,
    DemandAssistRequestSchema,
    DemandAssistResponseSchema,
    DemandBreakdownCompleteSchema,
    DemandCreateSchema,
    DemandGenerateStoriesSchema,
    DemandResponseSchema,
    DemandUpdateSchema,
    LinkedProjectSchema,
)
from codeforge.application.services.generation_context_assembler import assemble_generation_context
from codeforge.application.use_cases.run_demand_assistant import (
    DemandAssistantInput,
    run_demand_assistant,
)
from codeforge.application.use_cases.run_story_generation import (
    GenerationInput,
    run_story_generation,
)
from codeforge.domain.entities.demand import Demand, DemandStatus, LinkedProject
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_id import TeamId
from codeforge.infrastructure.ai.litellm_provider import LiteLLMProvider

router = APIRouter(prefix="/api/demands", tags=["demands"])

SKILLS_DIR = Path(__file__).parents[2] / "skills"


@router.post("", response_model=DemandResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_demand(
    payload: DemandCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    if payload.team_id is not None:
        team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    linked_projects = [
        LinkedProject(project_id=ProjectId(item.project_id), base_branch=item.base_branch)
        for item in payload.linked_projects
    ]
    demand, _ = Demand.create(
        title=payload.title,
        business_objective=payload.business_objective,
        team_id=TeamId(payload.team_id) if payload.team_id else None,
        acceptance_criteria=payload.acceptance_criteria,
        linked_projects=linked_projects,
    )
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.get("", response_model=list[DemandResponseSchema])
async def list_demands(
    status_filter: str | None = Query(default=None, alias="status"),
    team_id: str | None = Query(default=None),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[DemandResponseSchema]:
    try:
        status_value = DemandStatus(status_filter) if status_filter else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid status: {status_filter}",
        ) from None
    demands = await repositories.demand_repository.list_all(status=status_value)
    if team_id is not None:
        demands = [demand for demand in demands if str(demand.team_id) == team_id]
    return [_to_response(demand) for demand in demands]


@router.post("/assist", response_model=DemandAssistResponseSchema)
async def assist_demand(
    payload: DemandAssistRequestSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandAssistResponseSchema:
    project = await repositories.project_repository.get_by_id(ProjectId(payload.project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await run_demand_assistant(
        input=DemandAssistantInput(
            description=payload.description,
            project_id=project.id,
        ),
        provider=LiteLLMProvider(),
        model=ModelId(project.config.default_model),
        demand_repo=repositories.demand_repository,
        story_repo=repositories.story_repository,
    )
    return DemandAssistResponseSchema(
        demand=_to_response(result.demand),
        stories=[
            DemandAssistantStorySchema(
                title=story.title,
                description=story.description,
                acceptance_criteria=list(story.acceptance_criteria),
            )
            for story in result.stories
        ],
        success=result.success,
    )


@router.patch("/{demand_id}", response_model=DemandResponseSchema)
async def update_demand(
    demand_id: str,
    payload: DemandUpdateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found"
        )
    if payload.title is not None:
        demand.title = payload.title
    if payload.business_objective is not None:
        demand.business_objective = payload.business_objective
    if payload.team_id is not None:
        team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        demand.team_id = TeamId(payload.team_id)
    if payload.acceptance_criteria is not None:
        demand.acceptance_criteria = payload.acceptance_criteria
    if payload.linked_projects is not None:
        demand.linked_projects = [
            LinkedProject(
                project_id=ProjectId(lp.project_id),
                base_branch=lp.base_branch,
            )
            for lp in payload.linked_projects
        ]
    demand.updated_at = datetime.now(UTC)
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.get("/{demand_id}", response_model=DemandResponseSchema)
async def get_demand(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    return _to_response(demand)


@router.delete("/{demand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_demand(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    await repositories.demand_repository.delete(demand.id)


@router.post("/{demand_id}/activate", response_model=DemandResponseSchema)
async def activate_demand(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    demand.activate()
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.post("/{demand_id}/breakdown/request", response_model=DemandResponseSchema)
async def request_breakdown(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    demand.request_breakdown()
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.post("/{demand_id}/breakdown/complete", response_model=DemandResponseSchema)
async def complete_breakdown(
    demand_id: str,
    payload: DemandBreakdownCompleteSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    demand.complete_breakdown(total_tasks=payload.total_tasks)
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.post("/{demand_id}/generate-stories")
async def generate_stories(
    demand_id: str,
    request: Request,
    payload: DemandGenerateStoriesSchema | None = None,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> dict[str, str]:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found"
        )

    if not demand.linked_projects:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No linked projects",
        )

    jobs: dict[str, asyncio.Task] = request.app.state.generation_jobs
    existing = jobs.get(demand_id)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Story generation already in progress",
        )

    first_project = await repositories.project_repository.get_by_id(
        demand.linked_projects[0].project_id
    )
    model_id = (
        first_project.config.default_model
        if first_project
        else "anthropic:claude-sonnet-4-20250514"
    )

    async def _run() -> None:
        await run_story_generation(
            input=GenerationInput(
                demand_id=demand_id,
                skills_dir=SKILLS_DIR,
                model=model_id,
                selected_project_ids=(payload.selected_project_ids if payload else []),
                selected_document_ids=(payload.selected_document_ids if payload else []),
            ),
            demand_repo=repositories.demand_repository,
            project_repo=repositories.project_repository,
            repository_store=repositories.repository_store,
            story_repo=repositories.story_repository,
            provider=LiteLLMProvider(),
            team_document_repo=repositories.team_document_repository,
        )

    task = asyncio.create_task(_run())
    jobs[demand_id] = task
    task.add_done_callback(lambda _: jobs.pop(demand_id, None))

    return {"status": "generating"}


@router.get("/{demand_id}/generation-context")
async def get_demand_generation_context(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> dict:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demand not found",
        )
    if demand.team_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Demand has no team context",
        )

    summary = await assemble_generation_context(
        team_id=demand.team_id,
        demand_id=demand.id,
        project_repo=repositories.project_repository,
        repository_store=repositories.repository_store,
        team_document_repo=repositories.team_document_repository,
        demand_repo=repositories.demand_repository,
    )
    return {
        "team_id": str(summary.team_id),
        "demand_id": str(summary.demand_id),
        "selected_project_ids": [str(project_id) for project_id in summary.selected_project_ids],
        "selected_document_ids": summary.selected_document_ids,
        "projects_with_context": summary.projects_with_context,
        "projects_without_context": summary.projects_without_context,
        "items": [
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "preview": item.preview,
                "selected": item.selected,
                "source": item.source,
            }
            for item in summary.items
        ],
    }


@router.get("/{demand_id}/generation-stream")
async def generation_stream(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> StreamingResponse:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found"
        )

    async def _stream():
        for _ in range(600):
            await asyncio.sleep(1)
            d = await repositories.demand_repository.get_by_id(
                DemandId(demand_id)
            )
            if d is None:
                break

            gs = d.generation_status.value
            if gs == "done":
                yield f"data: {json.dumps({'status': 'done'})}\n\n"
                break
            elif gs == "error":
                msg = d.generation_error or "Generation failed"
                payload = json.dumps({"status": "error", "message": msg})
                yield f"data: {payload}\n\n"
                break
            else:
                yield f"data: {json.dumps({'status': gs})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


def _to_response(demand: Demand) -> DemandResponseSchema:
    return DemandResponseSchema(
        id=str(demand.id),
        title=demand.title,
        business_objective=demand.business_objective,
        team_id=str(demand.team_id) if demand.team_id else None,
        acceptance_criteria=list(demand.acceptance_criteria),
        linked_projects=[
            LinkedProjectSchema(
                project_id=str(project.project_id),
                base_branch=project.base_branch,
            )
            for project in demand.linked_projects
        ],
        status=demand.status.value,
        generation_status=demand.generation_status.value,
        generation_error=demand.generation_error,
        created_at=demand.created_at,
        updated_at=demand.updated_at,
    )
