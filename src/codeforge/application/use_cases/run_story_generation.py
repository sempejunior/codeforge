from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.services.generation_context_assembler import assemble_generation_context
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.services.team_context_assembler import assemble_team_context
from codeforge.application.services.workspace_context_assembler import (
    assemble_workspace_context,
)
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.application.use_cases.run_repository_analysis import (
    AnalysisInput,
    run_repository_analysis,
)
from codeforge.domain.entities.agent import AgentType, SessionOutcome
from codeforge.domain.entities.demand import Demand, GenerationStatus
from codeforge.domain.entities.repository import AnalysisStatus
from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.project_repository import ProjectRepositoryPort
from codeforge.domain.ports.repository_store import RepositoryStorePort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.ports.team_document_repository import TeamDocumentRepositoryPort
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId


@dataclass
class GenerationInput:
    demand_id: str
    skills_dir: Path
    model: str = "anthropic:claude-sonnet-4-20250514"
    selected_project_ids: list[str] | None = None
    selected_document_ids: list[str] | None = None


@dataclass
class GenerationEvent:
    stage: str
    message: str
    done: bool = False
    error: bool = False


class _StorySchema(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    technical_references: list[str] = Field(default_factory=list)


class _GenerationOutputSchema(BaseModel):
    stories: list[_StorySchema] = Field(default_factory=list)


async def run_story_generation(
    input: GenerationInput,
    demand_repo: DemandRepositoryPort,
    project_repo: ProjectRepositoryPort,
    repository_store: RepositoryStorePort,
    story_repo: StoryRepositoryPort,
    provider: AIProviderPort,
    on_event: Callable[[GenerationEvent], None] | None = None,
    team_document_repo: TeamDocumentRepositoryPort | None = None,
) -> list[Story]:
    demand = await demand_repo.get_by_id(DemandId(input.demand_id))
    if demand is None:
        raise ValueError(f"Demand {input.demand_id} not found")

    await _set_generation_status(
        demand, GenerationStatus.ANALYZING_PROJECTS, demand_repo
    )
    _emit(on_event, "analyzing_projects", "Analisando projetos vinculados...")

    selected_project_id_values = {
        project_id for project_id in (input.selected_project_ids or [])
    }
    selected_document_id_values = set(input.selected_document_ids or [])
    selected_project_ids = [
        ProjectId(project_id) for project_id in selected_project_id_values
    ] if selected_project_id_values else [
        linked_project.project_id for linked_project in demand.linked_projects
    ]

    context_parts: list[str] = []
    for lp in demand.linked_projects:
        if selected_project_id_values and str(lp.project_id) not in selected_project_id_values:
            continue
        project = await project_repo.get_by_id(lp.project_id)
        if project is None:
            logger.warning("Linked project {} not found, skipping", lp.project_id)
            continue

        repositories = await repository_store.list_by_project(lp.project_id)
        for repository in repositories:
            if repository.analysis_status != AnalysisStatus.DONE or not repository.context_doc:
                _emit(
                    on_event,
                    "analyzing_projects",
                    f"Analisando repositorio: {repository.name}...",
                )
                result = await run_repository_analysis(
                    AnalysisInput(repository_id=repository.id),
                    repository_store,
                    input.skills_dir,
                    None,
                )
                if result.success and result.context_doc:
                    context_parts.append(
                        f"## Repository: {repository.name} (Project: {project.name})\n\n{result.context_doc}"
                    )
                else:
                    logger.warning(
                        "Analysis failed for repository {}: {}",
                        repository.name,
                        result.error,
                    )
                    _emit(
                        on_event,
                        "analyzing_projects",
                        f"Analise falhou para {repository.name}: {result.error or 'unknown'}",
                    )
            else:
                context_parts.append(
                    f"## Repository: {repository.name} (Project: {project.name})\n\n{repository.context_doc}"
                )

    if demand.team_id is not None:
        team_context = await assemble_team_context(
            team_id=demand.team_id,
            project_repo=project_repo,
            repository_store=repository_store,
            selected_project_ids=selected_project_ids or None,
        )
        if team_context.consolidated_context:
            context_parts = [team_context.consolidated_context]

        if team_document_repo is not None:
            generation_context = await assemble_generation_context(
                team_id=demand.team_id,
                demand_id=demand.id,
                project_repo=project_repo,
                repository_store=repository_store,
                team_document_repo=team_document_repo,
                demand_repo=demand_repo,
                selected_project_ids=selected_project_ids,
                selected_document_ids=list(selected_document_id_values) or None,
            )
            workspace = await assemble_workspace_context(
                team_id=demand.team_id,
                project_repo=project_repo,
                repository_store=repository_store,
                team_document_repo=team_document_repo,
                demand_id=demand.id,
                demand_repo=demand_repo,
                selected_project_ids=generation_context.selected_project_ids,
                selected_document_ids=generation_context.selected_document_ids,
            )
            if workspace.consolidated_markdown:
                context_parts.append(workspace.consolidated_markdown)

    await _set_generation_status(
        demand, GenerationStatus.GENERATING_STORIES, demand_repo
    )
    _emit(on_event, "generating_stories", "Gerando stories...")

    extra_context = "\n\n---\n\n".join(context_parts) if context_parts else None

    prompt = (
        "Based on the demand below and the project context provided, "
        "generate well-scoped user stories for implementation. "
        "Each story should be independently deliverable and testable. "
        "Include technical_references with concrete files, modules, routers, services, "
        "models or endpoints that already appear in the provided context. "
        "Do not invent references that are not supported by the context.\n\n"
        f"Demand title: {demand.title}\n\n"
        f"Business objective:\n{demand.business_objective}\n\n"
    )
    if demand.acceptance_criteria:
        criteria = "\n".join(f"- {c}" for c in demand.acceptance_criteria)
        prompt += f"Acceptance criteria:\n{criteria}\n\n"
    prompt += "Return JSON only."

    result = await run_agent_session(
        config=SessionConfig(
            agent_type=AgentType.DEMAND_ASSISTANT,
            model=ModelId(input.model),
            system_prompt=build_system_prompt(
                AgentType.DEMAND_ASSISTANT,
                extra_context=extra_context,
            ),
            messages=[{"role": "user", "content": prompt}],
            tools={},
            max_steps=30,
            output_schema=_GenerationOutputSchema,
        ),
        provider=provider,
    )

    if (
        result.outcome != SessionOutcome.COMPLETED
        or result.structured_output is None
    ):
        raw = _extract_raw(result.messages)
        error_msg = f"Generation failed: {result.outcome.value}"
        if raw:
            error_msg += f" - {raw[:200]}"
        demand.generation_error = error_msg
        await _set_generation_status(
            demand, GenerationStatus.ERROR, demand_repo
        )
        _emit(on_event, "error", error_msg, error=True)
        return []

    parsed = result.structured_output
    if not isinstance(parsed, _GenerationOutputSchema):
        demand.generation_error = "Failed to parse generation output"
        await _set_generation_status(
            demand, GenerationStatus.ERROR, demand_repo
        )
        _emit(on_event, "error", "Failed to parse output", error=True)
        return []

    created_stories: list[Story] = []
    for item in parsed.stories:
        story, _ = Story.create(
            demand_id=demand.id,
            title=item.title,
            description=item.description,
            acceptance_criteria=list(item.acceptance_criteria),
            technical_references=list(item.technical_references),
            project_id=next(iter(selected_project_ids), None),
            status=StoryStatus.PROPOSED,
        )
        await story_repo.save(story)
        created_stories.append(story)

    demand.generation_error = None
    await _set_generation_status(demand, GenerationStatus.DONE, demand_repo)
    _emit(
        on_event,
        "done",
        f"Concluido: {len(created_stories)} stories geradas.",
        done=True,
    )

    return created_stories


async def _set_generation_status(
    demand: Demand,
    status: GenerationStatus,
    repo: DemandRepositoryPort,
) -> None:
    demand.generation_status = status
    demand.updated_at = datetime.now(UTC)
    await repo.save(demand)


def _emit(
    callback: Callable[[GenerationEvent], None] | None,
    stage: str,
    message: str,
    done: bool = False,
    error: bool = False,
) -> None:
    if callback is not None:
        callback(GenerationEvent(
            stage=stage, message=message, done=done, error=error
        ))


def _extract_raw(messages: list[dict]) -> str:
    parts = [
        m.get("content", "")
        for m in messages
        if m.get("role") == "assistant" and m.get("content")
    ]
    return "\n\n".join(parts)
