from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.generation_context import (
    GenerationContextItemSchema,
    GenerationContextResponseSchema,
)
from codeforge.api.schemas.team import TeamCreateSchema, TeamResponseSchema
from codeforge.api.schemas.team_context import (
    TeamContextRepositorySchema,
    TeamContextResponseSchema,
)
from codeforge.api.schemas.workspace_context import WorkspaceContextResponseSchema
from codeforge.application.services.generation_context_assembler import assemble_generation_context
from codeforge.application.services.team_context_assembler import assemble_team_context
from codeforge.application.services.workspace_context_assembler import (
    assemble_workspace_context,
)
from codeforge.domain.entities.team import Team
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_id import TeamId

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.post("", response_model=TeamResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamResponseSchema:
    team = Team.create(name=payload.name, description=payload.description)
    await repositories.team_repository.save(team)
    return _to_response(team)


@router.get("", response_model=list[TeamResponseSchema])
async def list_teams(
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[TeamResponseSchema]:
    teams = await repositories.team_repository.list_all()
    return [_to_response(team) for team in teams]


@router.get("/{team_id}", response_model=TeamResponseSchema)
async def get_team(
    team_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamResponseSchema:
    team = await repositories.team_repository.get_by_id(TeamId(team_id))
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return _to_response(team)


@router.get("/{team_id}/context", response_model=TeamContextResponseSchema)
async def get_team_context(
    team_id: str,
    project_ids: list[str] | None = Query(default=None),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TeamContextResponseSchema:
    typed_team_id = TeamId(team_id)
    team = await repositories.team_repository.get_by_id(typed_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    selected_project_ids = (
        [ProjectId(project_id) for project_id in project_ids]
        if project_ids
        else None
    )

    summary = await assemble_team_context(
        team_id=typed_team_id,
        project_repo=repositories.project_repository,
        repository_store=repositories.repository_store,
        selected_project_ids=selected_project_ids,
    )
    return TeamContextResponseSchema(
        team_id=str(summary.team_id),
        selected_project_ids=[str(project_id) for project_id in summary.selected_project_ids],
        ready_repositories=summary.ready_repositories,
        total_repositories=summary.total_repositories,
        missing_context_repositories=summary.missing_context_repositories,
        consolidated_context=summary.consolidated_context,
        repositories=[
            TeamContextRepositorySchema(
                repository_id=str(repo.repository_id),
                project_id=str(repo.project_id),
                project_name=repo.project_name,
                name=repo.name,
                path=repo.path,
                repo_url=repo.repo_url,
                source_label=repo.source_label,
                analysis_status=repo.analysis_status.value,
                analysis_executor=repo.analysis_executor,
                has_context=repo.has_context,
                is_selected=repo.is_selected,
                local_path_status=repo.local_path_status,
            )
            for repo in summary.repositories
        ],
    )


@router.get("/{team_id}/workspace-context", response_model=WorkspaceContextResponseSchema)
async def get_workspace_context(
    team_id: str,
    demand_id: str | None = Query(default=None),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> WorkspaceContextResponseSchema:
    typed_team_id = TeamId(team_id)
    team = await repositories.team_repository.get_by_id(typed_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    workspace = await assemble_workspace_context(
        team_id=typed_team_id,
        project_repo=repositories.project_repository,
        repository_store=repositories.repository_store,
        team_document_repo=repositories.team_document_repository,
        demand_id=DemandId(demand_id) if demand_id else None,
        demand_repo=repositories.demand_repository if demand_id else None,
    )
    return WorkspaceContextResponseSchema(
        team_id=team_id,
        consolidated_markdown=workspace.consolidated_markdown,
        documents_used=workspace.documents_used,
        projects_with_context=workspace.projects_with_context,
        projects_without_context=workspace.projects_without_context,
    )


@router.get("/{team_id}/generation-context", response_model=GenerationContextResponseSchema)
async def get_generation_context(
    team_id: str,
    demand_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> GenerationContextResponseSchema:
    typed_team_id = TeamId(team_id)
    team = await repositories.team_repository.get_by_id(typed_team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    summary = await assemble_generation_context(
        team_id=typed_team_id,
        demand_id=DemandId(demand_id),
        project_repo=repositories.project_repository,
        repository_store=repositories.repository_store,
        team_document_repo=repositories.team_document_repository,
        demand_repo=repositories.demand_repository,
    )
    return GenerationContextResponseSchema(
        team_id=team_id,
        demand_id=demand_id,
        selected_project_ids=[str(project_id) for project_id in summary.selected_project_ids],
        selected_document_ids=summary.selected_document_ids,
        projects_with_context=summary.projects_with_context,
        projects_without_context=summary.projects_without_context,
        items=[
            GenerationContextItemSchema(
                id=item.id,
                kind=item.kind,
                title=item.title,
                preview=item.preview,
                selected=item.selected,
                source=item.source,
            )
            for item in summary.items
        ],
    )


def _to_response(team: Team) -> TeamResponseSchema:
    return TeamResponseSchema(
        id=str(team.id),
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        updated_at=team.updated_at,
    )
