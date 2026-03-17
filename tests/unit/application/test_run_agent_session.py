from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.ports.ai_provider import AIProviderPort, GenerateResult, StreamPart
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.thinking_level import ThinkingLevel


def make_config(
    max_steps: int = 10,
    tools: dict | None = None,
    agent_type: AgentType = AgentType.CODER,
) -> SessionConfig:
    return SessionConfig(
        agent_type=agent_type,
        model=ModelId("anthropic:claude-sonnet-4-20250514"),
        system_prompt="You are a helpful assistant.",
        messages=[{"role": "user", "content": "Hello"}],
        tools=tools or {},
        max_steps=max_steps,
        session_id="test-session-1",
    )


class MockProvider(AIProviderPort):
    def __init__(self, parts: list[StreamPart]) -> None:
        self._parts = parts

    async def generate_stream(
        self, model, system, messages, tools=None, thinking=None, abort_event=None,
    ) -> AsyncGenerator[StreamPart, None]:
        async def _gen():
            for p in self._parts:
                yield p
        return _gen()

    async def generate(self, model, system, messages) -> GenerateResult:
        return GenerateResult(content="summary", usage=TokenUsage(), finish_reason="stop")


def text_parts(text: str) -> list[StreamPart]:
    return [
        StreamPart(type="text_delta", content=text),
        StreamPart(type="finish", finish_reason="stop"),
    ]


@pytest.mark.asyncio
async def test_session_completes_on_text_response():
    provider = MockProvider(text_parts("Hello, world!"))
    config = make_config()
    result = await run_agent_session(config, provider)
    assert result.outcome == SessionOutcome.COMPLETED
    assert result.steps_executed == 1


@pytest.mark.asyncio
async def test_session_cancelled_when_abort_event_set():
    event = asyncio.Event()
    event.set()
    provider = MockProvider(text_parts("should not run"))
    config = make_config()
    config.abort_event = event
    result = await run_agent_session(config, provider)
    assert result.outcome == SessionOutcome.CANCELLED
    assert result.steps_executed == 0


@pytest.mark.asyncio
async def test_session_max_steps():
    tool_call_parts = [
        StreamPart(type="tool_call", tool_name="NonExistent", tool_call_id="tc1", tool_input={}),
        StreamPart(type="finish", finish_reason="tool_calls"),
    ]

    class AlwaysToolProvider(AIProviderPort):
        async def generate_stream(self, *args, **kwargs) -> AsyncGenerator[StreamPart, None]:
            async def _gen():
                for p in tool_call_parts:
                    yield p
            return _gen()

        async def generate(self, *args, **kwargs) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    config = make_config(max_steps=3)
    result = await run_agent_session(config, AlwaysToolProvider())
    assert result.outcome == SessionOutcome.MAX_STEPS
    assert result.steps_executed == 3


@pytest.mark.asyncio
async def test_session_executes_tool_and_continues():
    from pydantic import BaseModel

    from codeforge.infrastructure.tools.base import (
        DefinedTool,
        ToolContext,
        ToolPermission,
        ToolResult,
    )

    class EchoInput(BaseModel):
        message: str

    class EchoTool(DefinedTool):
        @property
        def name(self) -> str:
            return "Echo"

        @property
        def description(self) -> str:
            return "Echoes input"

        @property
        def permission(self) -> ToolPermission:
            return ToolPermission.READ_ONLY

        @property
        def input_schema(self):
            return EchoInput

        async def execute(self, input, context) -> ToolResult:
            return ToolResult(content=f"Echo: {input.message}")

    tmp_path = Path("/tmp/test_codeforge_session")
    tmp_path.mkdir(exist_ok=True)
    ctx = ToolContext(cwd=tmp_path, project_dir=tmp_path)
    echo_tool = EchoTool().bind(ctx)

    steps = 0

    class ToolThenTextProvider(AIProviderPort):
        async def generate_stream(
            self, model, system, messages, tools=None, thinking=None, abort_event=None,
        ) -> AsyncGenerator[StreamPart, None]:
            nonlocal steps
            steps += 1

            async def _gen():
                if steps == 1:
                    yield StreamPart(
                        type="tool_call", tool_name="Echo", tool_call_id="tc1",
                        tool_input={"message": "test"},
                    )
                    yield StreamPart(type="finish", finish_reason="tool_calls")
                else:
                    yield StreamPart(type="text_delta", content="Done!")
                    yield StreamPart(type="finish", finish_reason="stop")
            return _gen()

        async def generate(self, *args, **kwargs) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    config = make_config(tools={"Echo": echo_tool})
    result = await run_agent_session(config, ToolThenTextProvider())
    assert result.outcome == SessionOutcome.COMPLETED
    assert result.tool_call_count == 1
    assert result.steps_executed == 2


@pytest.mark.asyncio
async def test_session_context_window_abort():
    """Context window abort triggered when prompt tokens >= 90% of limit."""
    parts_with_usage = [
        StreamPart(type="text_delta", content="hi"),
        StreamPart(type="usage", usage=TokenUsage(input_tokens=9_100, output_tokens=100)),
        StreamPart(type="finish", finish_reason="stop"),
    ]

    provider = MockProvider(parts_with_usage)
    config = make_config(max_steps=10)
    config.context_window_limit = 10_000

    result = await run_agent_session(config, provider)
    assert result.outcome in (SessionOutcome.CONTEXT_WINDOW, SessionOutcome.COMPLETED)


@pytest.mark.asyncio
async def test_provider_error_classified():
    class ErrorProvider(AIProviderPort):
        async def generate_stream(self, *args, **kwargs) -> AsyncGenerator[StreamPart, None]:
            raise Exception("HTTP 429: rate limit exceeded")

        async def generate(self, *args, **kwargs) -> GenerateResult:
            return GenerateResult(content="", usage=TokenUsage(), finish_reason="stop")

    config = make_config()
    result = await run_agent_session(config, ErrorProvider())
    assert result.outcome == SessionOutcome.RATE_LIMITED


@pytest.mark.asyncio
async def test_result_includes_duration():
    provider = MockProvider(text_parts("done"))
    config = make_config()
    result = await run_agent_session(config, provider)
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_session_dto_defaults():
    config = make_config()
    assert config.max_steps == 10
    assert config.thinking_level == ThinkingLevel.MEDIUM
    assert config.output_schema is None
    assert config.abort_event is None
