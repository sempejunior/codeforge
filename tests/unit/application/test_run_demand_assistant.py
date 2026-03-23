from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from codeforge.application.use_cases.run_demand_assistant import (
    DemandAssistantInput,
    run_demand_assistant,
)
from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.entities.demand import Demand
from codeforge.domain.entities.story import Story
from codeforge.domain.ports.ai_provider import AIProviderPort, GenerateResult, StreamPart
from codeforge.domain.ports.demand_repository import DemandRepositoryPort
from codeforge.domain.ports.story_repository import StoryRepositoryPort
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.sprint_id import SprintId
from codeforge.domain.value_objects.story_id import StoryId


class _MockProvider(AIProviderPort):
    def __init__(self, content: str) -> None:
        self._content = content

    async def generate_stream(
        self,
        model,
        system,
        messages,
        tools=None,
        thinking=None,
        abort_event=None,
    ) -> AsyncGenerator[StreamPart, None]:
        del model, system, messages, tools, thinking, abort_event

        async def _gen() -> AsyncGenerator[StreamPart, None]:
            yield StreamPart(type="text_delta", content=self._content)
            yield StreamPart(type="finish", finish_reason="stop")

        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        del model, system, messages
        return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")


class _DemandRepo(DemandRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Demand] = []

    async def save(self, demand: Demand) -> None:
        self.saved.append(demand)

    async def get_by_id(self, demand_id: DemandId) -> Demand | None:
        del demand_id
        return None

    async def list_all(self, status=None) -> list[Demand]:
        del status
        return []

    async def delete(self, demand_id: DemandId) -> None:
        del demand_id


class _StoryRepo(StoryRepositoryPort):
    def __init__(self) -> None:
        self.saved: list[Story] = []

    async def save(self, story: Story) -> None:
        self.saved.append(story)

    async def get_by_id(self, story_id: StoryId) -> Story | None:
        del story_id
        return None

    async def list_by_demand(self, demand_id: DemandId, status=None) -> list[Story]:
        del demand_id, status
        return []

    async def list_by_sprint(self, sprint_id: SprintId) -> list[Story]:
        del sprint_id
        return []

    async def delete(self, story_id: StoryId) -> None:
        del story_id


@pytest.mark.asyncio
async def test_run_demand_assistant_returns_structured_entities() -> None:
    provider = _MockProvider(
        """
        {
          "objective": "Increase checkout conversion",
          "acceptance_criteria": ["PIX available"],
          "stories": [
            {
              "title": "Backend PIX API",
              "description": "Implement PIX API",
              "acceptance_criteria": ["POST /payments/pix"]
            }
          ]
        }
        """
    )
    demand_repo = _DemandRepo()
    story_repo = _StoryRepo()

    result = await run_demand_assistant(
        input=DemandAssistantInput(
            description="Precisamos de checkout com pix",
            project_id=ProjectId.generate(),
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        demand_repo=demand_repo,
        story_repo=story_repo,
    )

    assert result.success is True
    assert result.demand.business_objective == "Increase checkout conversion"
    assert len(result.stories) == 1
    assert len(demand_repo.saved) == 1
    assert len(story_repo.saved) == 1


@pytest.mark.asyncio
async def test_run_demand_assistant_returns_failure_for_unstructured_output() -> None:
    provider = _MockProvider("no structured output")

    result = await run_demand_assistant(
        input=DemandAssistantInput(
            description="Texto livre",
            project_id=ProjectId.generate(),
        ),
        provider=provider,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        demand_repo=_DemandRepo(),
        story_repo=_StoryRepo(),
        persist=False,
    )

    assert result.success is False
    assert result.stories == []
