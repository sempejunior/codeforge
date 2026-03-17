from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.ports.ai_provider import (
    AIProviderPort,
    GenerateResult,
    Message,
    StreamPart,
)
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.thinking_level import ThinkingLevel

logger = logging.getLogger(__name__)

_THINKING_BUDGET: dict[ThinkingLevel, int] = {
    ThinkingLevel.LOW: 1_024,
    ThinkingLevel.MEDIUM: 8_000,
    ThinkingLevel.HIGH: 16_000,
}

_MODELS_SUPPORTING_THINKING: frozenset[str] = frozenset({
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-3-7-sonnet",
    "claude-3-5-sonnet",
    "claude-3-5-haiku",
})


def _supports_thinking(model: str) -> bool:
    return any(m in model for m in _MODELS_SUPPORTING_THINKING)


def _to_litellm_messages(messages: list[Message]) -> list[dict]:
    result = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.name:
            msg["name"] = m.name
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        result.append(msg)
    return result


def _build_litellm_tools(bound_tools: list[Any]) -> list[dict]:
    """Converts BoundTool list to LiteLLM tool format."""
    result = []
    for bt in bound_tools:
        schema = bt.input_schema.model_json_schema()
        result.append({
            "type": "function",
            "function": {
                "name": bt.name,
                "description": bt.description,
                "parameters": schema,
            },
        })
    return result


def _extract_usage(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage()
    cache_read = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None and hasattr(details, "get"):
        cache_read = details.get("cached_tokens", 0)
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_tokens", 0),
        output_tokens=getattr(usage, "completion_tokens", 0),
        cache_read_tokens=cache_read,
    )


class LiteLLMProvider(AIProviderPort):
    """AI provider adapter using LiteLLM for multi-provider support."""

    def __init__(self, default_api_key: str | None = None) -> None:
        self._default_api_key = default_api_key

    async def generate_stream(
        self,
        model: ModelId,
        system: str,
        messages: list[Message],
        tools: list[Any] | None = None,
        thinking: ThinkingLevel = ThinkingLevel.MEDIUM,
        abort_event: Any | None = None,
    ) -> AsyncGenerator[StreamPart, None]:
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm is not installed. Run: pip install litellm") from exc

        litellm_model = self._resolve_model(model)
        all_messages = [{"role": "system", "content": system}]
        all_messages.extend(_to_litellm_messages(messages))

        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": all_messages,
            "stream": True,
        }

        if tools:
            kwargs["tools"] = _build_litellm_tools(tools)
            kwargs["tool_choice"] = "auto"

        if _supports_thinking(model.model) and thinking != ThinkingLevel.LOW:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": _THINKING_BUDGET[thinking],
            }

        return self._stream_generator(litellm, kwargs, abort_event)

    async def _stream_generator(
        self,
        litellm: Any,
        kwargs: dict,
        abort_event: Any | None,
    ) -> AsyncGenerator[StreamPart, None]:
        pending_tool_calls: dict[str, dict] = {}

        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                if abort_event and abort_event.is_set():
                    break

                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                if delta.content:
                    yield StreamPart(type="text_delta", content=delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = str(tc.index) if hasattr(tc, "index") else "0"
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "" if tc.function else "",
                                "arguments": "",
                            }
                        if tc.function and tc.function.arguments:
                            pending_tool_calls[idx]["arguments"] += tc.function.arguments
                        if tc.id:
                            pending_tool_calls[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            pending_tool_calls[idx]["name"] = tc.function.name

                finish_reason = chunk.choices[0].finish_reason if chunk.choices else None
                if finish_reason in ("tool_calls", "stop") and pending_tool_calls:
                    for tc_data in pending_tool_calls.values():
                        try:
                            tool_input = (
                                json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                            )
                        except json.JSONDecodeError:
                            tool_input = {}
                        yield StreamPart(
                            type="tool_call",
                            tool_name=tc_data["name"],
                            tool_call_id=tc_data["id"],
                            tool_input=tool_input,
                        )
                    pending_tool_calls.clear()

                if hasattr(chunk, "usage") and chunk.usage:
                    yield StreamPart(
                        type="usage",
                        usage=TokenUsage(
                            input_tokens=getattr(chunk.usage, "prompt_tokens", 0),
                            output_tokens=getattr(chunk.usage, "completion_tokens", 0),
                        ),
                    )

        except Exception as exc:
            error_msg = str(exc)
            logger.exception("LiteLLM stream error: %s", error_msg)
            yield StreamPart(type="error", content=error_msg)

        yield StreamPart(type="finish", finish_reason="stop")

    async def generate(
        self,
        model: ModelId,
        system: str,
        messages: list[Message],
    ) -> GenerateResult:
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm is not installed.") from exc

        litellm_model = self._resolve_model(model)
        all_messages = [{"role": "system", "content": system}]
        all_messages.extend(_to_litellm_messages(messages))

        response = await litellm.acompletion(
            model=litellm_model,
            messages=all_messages,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        return GenerateResult(
            content=content,
            usage=_extract_usage(response),
            finish_reason=response.choices[0].finish_reason or "stop",
        )

    def _resolve_model(self, model: ModelId) -> str:
        """Converts 'provider:model' to LiteLLM format."""
        provider = model.provider
        model_name = model.model
        if provider == "anthropic":
            return model_name
        if provider == "openai":
            return model_name
        return f"{provider}/{model_name}"
