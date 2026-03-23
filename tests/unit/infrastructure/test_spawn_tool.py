from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.ports.ai_provider import AIProviderPort, GenerateResult, StreamPart
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import ToolContext
from codeforge.infrastructure.tools.registry import build_default_registry
from codeforge.infrastructure.tools.spawn_tool import SpawnInput, SpawnTool


class _MockProvider(AIProviderPort):
    def __init__(self, text: str = "Sub-agent completed the task.") -> None:
        self._text = text

    async def generate_stream(
        self, model, system, messages, tools=None, thinking=None, abort_event=None,
    ) -> AsyncGenerator[StreamPart, None]:
        async def _gen():
            yield StreamPart(type="text_delta", content=self._text)
            yield StreamPart(type="finish", finish_reason="stop")
        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        return GenerateResult(content=self._text, usage=TokenUsage(), finish_reason="stop")


@pytest.fixture
def ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(cwd=tmp_path, project_dir=tmp_path)


@pytest.fixture
def model() -> ModelId:
    return ModelId("anthropic:claude-sonnet-4-20250514")


@pytest.fixture
def tool(model: ModelId) -> SpawnTool:
    return SpawnTool(
        provider=_MockProvider(),
        model=model,
        registry=build_default_registry(),
    )


async def test_spawn_coder(tool: SpawnTool, ctx: ToolContext) -> None:
    result = await tool.execute(
        SpawnInput(task="Write hello world", agent_type="coder"), ctx
    )
    assert not result.is_error
    assert "Sub-agent completed" in result.content


async def test_spawn_breakdown(tool: SpawnTool, ctx: ToolContext) -> None:
    result = await tool.execute(
        SpawnInput(task="Break down the story", agent_type="breakdown"), ctx
    )
    assert not result.is_error


async def test_spawn_invalid_agent_type(tool: SpawnTool, ctx: ToolContext) -> None:
    result = await tool.execute(
        SpawnInput(task="Do something", agent_type="nonexistent"), ctx
    )
    assert result.is_error
    assert "Unknown agent type" in result.content


async def test_spawn_disallowed_agent_type(tool: SpawnTool, ctx: ToolContext) -> None:
    result = await tool.execute(
        SpawnInput(task="Do something", agent_type="spec_writer"), ctx
    )
    assert result.is_error
    assert "not allowed" in result.content


async def test_spawn_returns_sub_agent_output(
    model: ModelId, ctx: ToolContext
) -> None:
    provider = _MockProvider(text="Custom output from sub-agent")
    tool = SpawnTool(provider=provider, model=model, registry=build_default_registry())
    result = await tool.execute(
        SpawnInput(task="Do work", agent_type="coder"), ctx
    )
    assert "Custom output from sub-agent" in result.content


async def test_spawn_error_outcome(model: ModelId, ctx: ToolContext) -> None:
    class _ErrorProvider(AIProviderPort):
        async def generate_stream(
            self, model, system, messages,
            tools=None, thinking=None, abort_event=None,
        ):
            async def _gen():
                yield StreamPart(type="error", content="API error")
            return _gen()

        async def generate(self, model, system, messages) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    tool = SpawnTool(
        provider=_ErrorProvider(), model=model, registry=build_default_registry()
    )
    result = await tool.execute(
        SpawnInput(task="Do work", agent_type="coder"), ctx
    )
    assert result.is_error


async def test_spawn_properties(tool: SpawnTool) -> None:
    assert tool.name == "Spawn"
    assert tool.input_schema is SpawnInput
    assert "sub-agent" in tool.description.lower()
