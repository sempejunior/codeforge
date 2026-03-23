from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_agent_session import run_agent_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import (
    DefinedTool,
    ToolContext,
    ToolPermission,
    ToolResult,
)
from codeforge.infrastructure.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_ALLOWED_SUB_AGENTS: frozenset[str] = frozenset({
    AgentType.BREAKDOWN,
    AgentType.COMPLEXITY_ASSESSOR,
    AgentType.CODER,
    AgentType.QA_REVIEWER,
})


class SpawnInput(BaseModel):
    task: str = Field(description="The task description for the sub-agent")
    agent_type: str = Field(
        default=AgentType.CODER,
        description="The agent type to spawn (coder, breakdown, complexity_assessor, qa_reviewer)",
    )
    label: str | None = Field(default=None, description="Short label for tracking")


class SpawnTool(DefinedTool):
    """Spawns a sub-agent session to handle a delegated task.

    Runs the sub-agent inline (not background) using the existing
    ``run_agent_session`` loop. The result text is returned to the
    calling agent.  Adapted from nanobot/agent/tools/spawn.py.
    """

    def __init__(
        self,
        provider: AIProviderPort,
        model: ModelId,
        registry: ToolRegistry,
    ) -> None:
        self._provider = provider
        self._model = model
        self._registry = registry

    @property
    def name(self) -> str:
        return "Spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a sub-agent to handle a delegated task. "
            "The sub-agent runs to completion and returns its output. "
            "Use for tasks that benefit from a separate agent context."
        )

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    @property
    def input_schema(self) -> type[SpawnInput]:
        return SpawnInput

    async def execute(self, input: SpawnInput, context: ToolContext) -> ToolResult:
        try:
            agent_type = AgentType(input.agent_type)
        except ValueError:
            return ToolResult(
                content=f"Unknown agent type: {input.agent_type!r}. "
                f"Use one of: {', '.join(sorted(_ALLOWED_SUB_AGENTS))}",
                is_error=True,
            )

        if agent_type not in _ALLOWED_SUB_AGENTS:
            return ToolResult(
                content=f"Agent type {agent_type!r} is not allowed for spawning. "
                f"Use one of: {', '.join(sorted(_ALLOWED_SUB_AGENTS))}",
                is_error=True,
            )

        tools = self._registry.get_tools_for_agent(agent_type, context)
        system_prompt = build_system_prompt(
            agent_type, project_path=context.project_dir
        )
        label = input.label or input.task[:60]
        logger.info("Spawning sub-agent %s: %s", agent_type, label)

        result = await run_agent_session(
            config=SessionConfig(
                agent_type=agent_type,
                model=self._model,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": input.task}],
                tools=tools,
            ),
            provider=self._provider,
        )

        if result.outcome == SessionOutcome.COMPLETED:
            output = _extract_output(result.messages)
            return ToolResult(content=output or "(sub-agent produced no output)")

        error_detail = result.error or result.outcome.value
        return ToolResult(
            content=f"Sub-agent finished with outcome={result.outcome.value}: {error_detail}",
            is_error=result.outcome != SessionOutcome.COMPLETED,
        )


def _extract_output(messages: list[dict]) -> str:
    parts = [
        m.get("content", "")
        for m in messages
        if m.get("role") == "assistant" and m.get("content")
    ]
    return "\n\n".join(parts)
