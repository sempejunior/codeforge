from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome
from codeforge.domain.entities.demand import Demand, LinkedProject
from codeforge.domain.entities.story import Story
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId


@dataclass
class DemandAssistantInput:
    description: str
    project_id: ProjectId


@dataclass
class DemandAssistantResult:
    demand: Demand
    stories: list[Story]
    success: bool


class _DemandAssistantStorySchema(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class _DemandAssistantOutputSchema(BaseModel):
    objective: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    stories: list[_DemandAssistantStorySchema] = Field(default_factory=list)


async def run_demand_assistant(
    input: DemandAssistantInput,
    provider: AIProviderPort,
    model: ModelId,
    demand_repo: DemandRepositoryPort,
    story_repo: StoryRepositoryPort,
    persist: bool = True,
) -> DemandAssistantResult:
    prompt = (
        "Structure the following free-form demand into a business objective, acceptance criteria, "
        "and independently deliverable stories. Return JSON only.\n\n"
        f"Description:\n{input.description}"
    )

    result = await run_agent_session(
        config=SessionConfig(
            agent_type=AgentType.DEMAND_ASSISTANT,
            model=model,
            system_prompt=build_system_prompt(AgentType.DEMAND_ASSISTANT),
            messages=[{"role": "user", "content": prompt}],
            tools={},
            max_steps=20,
            output_schema=_DemandAssistantOutputSchema,
        ),
        provider=provider,
    )

    if result.outcome != SessionOutcome.COMPLETED or result.structured_output is None:
        fallback_demand, _ = Demand.create(
            title=_derive_demand_title(input.description),
            business_objective=input.description,
            acceptance_criteria=[],
            linked_projects=[LinkedProject(project_id=input.project_id)],
        )
        return DemandAssistantResult(demand=fallback_demand, stories=[], success=False)

    parsed = result.structured_output
    if not isinstance(parsed, _DemandAssistantOutputSchema):
        fallback_demand, _ = Demand.create(
            title=_derive_demand_title(input.description),
            business_objective=input.description,
            acceptance_criteria=[],
            linked_projects=[LinkedProject(project_id=input.project_id)],
        )
        return DemandAssistantResult(demand=fallback_demand, stories=[], success=False)
    demand, _ = Demand.create(
        title=_derive_demand_title(parsed.objective),
        business_objective=parsed.objective,
        acceptance_criteria=list(parsed.acceptance_criteria),
        linked_projects=[LinkedProject(project_id=input.project_id)],
    )
    stories: list[Story] = []
    for item in parsed.stories:
        story, _ = Story.create(
            demand_id=demand.id,
            title=item.title,
            description=item.description,
            acceptance_criteria=list(item.acceptance_criteria),
        )
        stories.append(story)

    if persist:
        await demand_repo.save(demand)
        for story in stories:
            await story_repo.save(story)

    return DemandAssistantResult(demand=demand, stories=stories, success=True)


def _derive_demand_title(text: str) -> str:
    words = " ".join(text.strip().split())
    if not words:
        return "New demand"
    if len(words) <= 80:
        return words
    return f"{words[:77].rstrip()}..."
