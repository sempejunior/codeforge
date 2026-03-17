from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from ..entities.agent import TokenUsage
from ..value_objects.model_id import ModelId
from ..value_objects.thinking_level import ThinkingLevel


@dataclass
class Message:
    role: str
    content: str | list[dict]
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class StreamPart:
    type: str
    content: str = ""
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_input: dict | None = None
    usage: TokenUsage | None = None
    finish_reason: str | None = None


@dataclass
class GenerateResult:
    content: str
    usage: TokenUsage
    finish_reason: str


class AIProviderPort(ABC):
    @abstractmethod
    async def generate_stream(
        self,
        model: ModelId,
        system: str,
        messages: list[Message],
        tools: list[Any] | None = None,
        thinking: ThinkingLevel = ThinkingLevel.MEDIUM,
        abort_event: Any | None = None,
    ) -> AsyncGenerator[StreamPart, None]: ...

    @abstractmethod
    async def generate(
        self,
        model: ModelId,
        system: str,
        messages: list[Message],
    ) -> GenerateResult: ...
