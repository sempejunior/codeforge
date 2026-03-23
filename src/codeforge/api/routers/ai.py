from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.ai import InlineAssistRequestSchema, InlineAssistResponseSchema
from codeforge.application.services.team_context_assembler import assemble_team_context
from codeforge.application.services.workspace_context_assembler import assemble_workspace_context
from codeforge.domain.ports.ai_provider import Message
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.team_id import TeamId
from codeforge.infrastructure.ai.litellm_provider import LiteLLMProvider

router = APIRouter(prefix="/api/ai", tags=["ai"])

_DEFAULT_MODEL = "anthropic:claude-sonnet-4-20250514"
_ACTIONS: dict[str, str] = {
    "improve": (
        "Rewrite the text with better clarity, stronger structure, "
        "and more precise wording."
    ),
    "expand": "Expand the text with more concrete technical detail while preserving intent.",
    "simplify": (
        "Rewrite the text using simpler language and shorter sentences "
        "without losing meaning."
    ),
    "translate_en": "Translate the text to clear professional English.",
    "suggest_acceptance_criteria": (
        "Return only a concise bullet list of acceptance criteria, "
        "one item per line, in Portuguese."
    ),
}


@router.post("/inline-assist", response_model=InlineAssistResponseSchema)
async def inline_assist(
    payload: InlineAssistRequestSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> InlineAssistResponseSchema:
    instruction = _ACTIONS.get(payload.action)
    if instruction is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported action: {payload.action}",
        )

    team_id = await _resolve_team_id(payload, repositories)
    context_parts: list[str] = []
    if team_id is not None:
        team_context = await assemble_team_context(
            team_id=team_id,
            project_repo=repositories.project_repository,
            repository_store=repositories.repository_store,
        )
        if team_context.consolidated_context:
            context_parts.append(team_context.consolidated_context)
        workspace_context = await assemble_workspace_context(
            team_id=team_id,
            project_repo=repositories.project_repository,
            repository_store=repositories.repository_store,
            team_document_repo=repositories.team_document_repository,
            demand_id=DemandId(payload.demand_id) if payload.demand_id else None,
            demand_repo=repositories.demand_repository if payload.demand_id else None,
        )
        if workspace_context.consolidated_markdown:
            context_parts.append(workspace_context.consolidated_markdown)

    if payload.project_id:
        project = await repositories.project_repository.get_by_id(ProjectId(payload.project_id))
        if project is not None:
            project_repos = await repositories.repository_store.list_by_project(project.id)
            for repo in project_repos:
                if repo.context_doc:
                    context_parts.append(
                        f"## Repository: {repo.name} (Project: {project.name})\n\n{repo.context_doc}"
                    )

    provider = LiteLLMProvider()
    model = ModelId(await _resolve_model(payload, repositories))
    system = (
        "You are the inline writing assistant for CodeForge. "
        "Return only the transformed text requested by the user, with no preamble."
    )
    if context_parts:
        system = f"{system}\n\nContext:\n\n" + "\n\n---\n\n".join(context_parts)

    result = await provider.generate(
        model=model,
        system=system,
        messages=[
            Message(
                role="user",
                content=(
                    f"Action: {payload.action}\n"
                    f"Instruction: {instruction}\n\n"
                    f"Text:\n{payload.text}"
                ),
            )
        ],
    )
    return InlineAssistResponseSchema(result=result.content.strip())


async def _resolve_team_id(
    payload: InlineAssistRequestSchema,
    repositories: RepositoryContainer,
) -> TeamId | None:
    if payload.team_id:
        team = await repositories.team_repository.get_by_id(TeamId(payload.team_id))
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        return team.id
    if payload.demand_id:
        demand = await repositories.demand_repository.get_by_id(DemandId(payload.demand_id))
        if demand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand not found")
        return demand.team_id
    if payload.project_id:
        project = await repositories.project_repository.get_by_id(ProjectId(payload.project_id))
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project.team_id
    return None


async def _resolve_model(
    payload: InlineAssistRequestSchema,
    repositories: RepositoryContainer,
) -> str:
    if payload.project_id:
        project = await repositories.project_repository.get_by_id(ProjectId(payload.project_id))
        if project is not None:
            return project.config.default_model
    if payload.demand_id:
        demand = await repositories.demand_repository.get_by_id(DemandId(payload.demand_id))
        if demand is not None and demand.linked_projects:
            project = await repositories.project_repository.get_by_id(
                demand.linked_projects[0].project_id
            )
            if project is not None:
                return project.config.default_model
    return _DEFAULT_MODEL
