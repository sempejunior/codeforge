from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.thinking_level import ThinkingLevel
from codeforge.infrastructure.tools.base import BoundTool


@dataclass
class SessionConfig:
    """Configuration for a single agent session."""

    agent_type: AgentType
    model: ModelId
    system_prompt: str
    messages: list[dict]
    tools: dict[str, BoundTool] = field(default_factory=dict)
    max_steps: int = 500
    context_window_limit: int = 200_000
    thinking_level: ThinkingLevel = ThinkingLevel.MEDIUM
    output_schema: type[BaseModel] | None = None
    abort_event: asyncio.Event | None = None
    task_id: str = ""
    session_id: str = ""


@dataclass
class SessionResult:
    """Result of a completed agent session."""

    outcome: SessionOutcome
    steps_executed: int = 0
    tool_call_count: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    messages: list[dict] = field(default_factory=list)
    structured_output: Any | None = None
    error: str | None = None
    duration_ms: int = 0
    continuation_count: int = 0
