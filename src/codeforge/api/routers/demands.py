from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.demand import (
    DemandBreakdownCompleteSchema,
    DemandCreateSchema,
    DemandResponseSchema,
    LinkedProjectSchema,
)
from codeforge.domain.entities.demand import Demand, DemandStatus, LinkedProject
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.project_id import ProjectId

router = APIRouter(prefix="/api/demands", tags=["demands"])


@router.post("", response_model=DemandResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_demand(
    payload: DemandCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    linked_projects = [
        LinkedProject(project_id=ProjectId(item.project_id), base_branch=item.base_branch)
        for item in payload.linked_projects
    ]
    demand, _ = Demand.create(
        title=payload.title,
        business_objective=payload.business_objective,
        acceptance_criteria=payload.acceptance_criteria,
        linked_projects=linked_projects,
    )
    await repositories.demand_repository.save(demand)
    return _to_response(demand)


@router.get("", response_model=list[DemandResponseSchema])
async def list_demands(
    status_filter: str | None = Query(default=None, alias="status"),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[DemandResponseSchema]:
    status_value = DemandStatus(status_filter) if status_filter else None
    demands = await repositories.demand_repository.list_all(status=status_value)
    return [_to_response(demand) for demand in demands]


@router.get("/{demand_id}", response_model=DemandResponseSchema)
async def get_demand(
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> DemandResponseSchema:
    demand = await repositories.demand_repository.get_by_id(DemandId(demand_id))
    if demand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
    return _to_response(demand)


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


def _to_response(demand: Demand) -> DemandResponseSchema:
    return DemandResponseSchema(
        id=str(demand.id),
        title=demand.title,
        business_objective=demand.business_objective,
        acceptance_criteria=list(demand.acceptance_criteria),
        linked_projects=[
            LinkedProjectSchema(
                project_id=str(project.project_id),
                base_branch=project.base_branch,
            )
            for project in demand.linked_projects
        ],
        status=demand.status.value,
        created_at=demand.created_at,
        updated_at=demand.updated_at,
    )
