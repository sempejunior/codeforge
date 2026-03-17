from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from codeforge.application.dto.agent_session_dto import SessionConfig, SessionResult
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.ports.ai_provider import AIProviderPort, Message
from codeforge.infrastructure.security.error_classifier import classify_error

logger = logging.getLogger(__name__)

_CONTEXT_WARN_PCT = 0.85
_CONTEXT_ABORT_PCT = 0.90

_CONVERGENCE_NUDGE_PCT = 0.75

_NUDGE_AGENT_TYPES: frozenset[AgentType] = frozenset({
    AgentType.QA_REVIEWER,
    AgentType.QA_FIXER,
    AgentType.SPEC_CRITIC,
})

_STREAM_INACTIVITY_TIMEOUT_S = 60.0

_CONTEXT_WARN_MSG = (
    "WARNING: You are approaching the context window limit ({pct:.0f}% used). "
    "Begin wrapping up your work. Prioritize completing your current task."
)

_CONVERGENCE_NUDGE_MSG = (
    "IMPORTANT: You have used {used} of {total} steps ({remaining} remaining). "
    "You must finalize your output now. Write all required files and stop."
)


async def run_agent_session(
    config: SessionConfig,
    provider: AIProviderPort,
) -> SessionResult:
    """Runs a single agentic session: stream text + execute tool calls in a loop."""
    session_id = config.session_id or str(uuid.uuid4())
    start_ms = int(time.time() * 1000)
    max_steps = config.max_steps
    context_limit = config.context_window_limit

    messages: list[dict] = list(config.messages)
    total_usage = TokenUsage()
    steps_executed = 0
    tool_call_count = 0
    context_warn_injected = False
    convergence_nudge_injected = False
    last_prompt_tokens = 0

    logger.info(
        "Session %s started: agent=%s model=%s max_steps=%d",
        session_id,
        config.agent_type,
        config.model,
        max_steps,
    )

    while steps_executed < max_steps:
        if config.abort_event and config.abort_event.is_set():
            return _make_result(
                SessionOutcome.CANCELLED,
                steps_executed,
                tool_call_count,
                total_usage,
                messages,
                start_ms,
            )

        system_injections: list[str] = []

        if last_prompt_tokens > 0 and context_limit > 0:
            pct = last_prompt_tokens / context_limit

            if pct >= _CONTEXT_ABORT_PCT:
                logger.warning(
                    "Session %s: context window abort at %.0f%%", session_id, pct * 100
                )
                return _make_result(
                    SessionOutcome.CONTEXT_WINDOW,
                    steps_executed,
                    tool_call_count,
                    total_usage,
                    messages,
                    start_ms,
                )

            if pct >= _CONTEXT_WARN_PCT and not context_warn_injected:
                system_injections.append(_CONTEXT_WARN_MSG.format(pct=pct * 100))
                context_warn_injected = True

        if (
            config.agent_type in _NUDGE_AGENT_TYPES
            and steps_executed >= max_steps * _CONVERGENCE_NUDGE_PCT
            and not convergence_nudge_injected
        ):
            remaining = max_steps - steps_executed
            system_injections.append(
                _CONVERGENCE_NUDGE_MSG.format(
                    used=steps_executed, total=max_steps, remaining=remaining
                )
            )
            convergence_nudge_injected = True

        step_messages = list(messages)
        for injection in system_injections:
            step_messages.append({"role": "user", "content": injection})

        msg_objects = [
            Message(
                role=m["role"],
                content=m.get("content", ""),
                tool_call_id=m.get("tool_call_id"),
                name=m.get("name"),
            )
            for m in step_messages
        ]

        try:
            step_result = await _execute_step(
                provider=provider,
                config=config,
                messages=msg_objects,
                session_id=session_id,
            )
        except Exception as exc:
            outcome, err_msg = classify_error(exc)
            logger.error("Session %s step error: %s -> %s", session_id, err_msg, outcome)
            return _make_result(
                outcome,
                steps_executed,
                tool_call_count,
                total_usage,
                messages,
                start_ms,
                error=err_msg,
            )

        steps_executed += 1

        if step_result.usage:
            _add_usage(total_usage, step_result.usage)
            last_prompt_tokens = step_result.usage.input_tokens

        if step_result.assistant_content:
            messages.append({"role": "assistant", "content": step_result.assistant_content})

        if step_result.tool_calls:
            for tc in step_result.tool_calls:
                tool_call_count += 1
                tool_output = await _execute_tool_call(tc, config.tools, session_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_output,
                })
            continue

        if step_result.finish_reason in ("stop", "end_turn", None):
            logger.info(
                "Session %s completed: steps=%d tool_calls=%d tokens=%d",
                session_id,
                steps_executed,
                tool_call_count,
                total_usage.total,
            )
            return _make_result(
                SessionOutcome.COMPLETED,
                steps_executed,
                tool_call_count,
                total_usage,
                messages,
                start_ms,
                structured_output=step_result.structured_output,
            )

    logger.warning("Session %s: max_steps (%d) reached", session_id, max_steps)
    return _make_result(
        SessionOutcome.MAX_STEPS,
        steps_executed,
        tool_call_count,
        total_usage,
        messages,
        start_ms,
    )


async def _execute_step(
    provider: AIProviderPort,
    config: SessionConfig,
    messages: list[Message],
    session_id: str,
) -> _StepResult:
    """Executes one LLM step: stream -> collect text + tool calls."""
    text_parts: list[str] = []
    tool_calls: list[dict] = []
    usage: TokenUsage | None = None
    finish_reason: str | None = None

    bound_tools = list(config.tools.values()) if config.tools else None

    stream = await provider.generate_stream(
        model=config.model,
        system=config.system_prompt,
        messages=messages,
        tools=bound_tools,
        thinking=config.thinking_level,
        abort_event=config.abort_event,
    )

    async for part in stream:
        if part.type == "text_delta":
            text_parts.append(part.content)
        elif part.type == "tool_call":
            tool_calls.append({
                "id": part.tool_call_id or str(uuid.uuid4()),
                "name": part.tool_name or "",
                "input": part.tool_input or {},
            })
        elif part.type == "usage" and part.usage:
            usage = part.usage
        elif part.type == "finish":
            finish_reason = part.finish_reason
        elif part.type == "error":
            raise RuntimeError(f"Stream error: {part.content}")

    assistant_content = "".join(text_parts) if text_parts else None

    structured_output = None
    if config.output_schema and assistant_content:
        structured_output = _try_parse_structured(assistant_content, config.output_schema)

    return _StepResult(
        assistant_content=assistant_content,
        tool_calls=tool_calls if tool_calls else None,
        usage=usage,
        finish_reason=finish_reason,
        structured_output=structured_output,
    )


async def _execute_tool_call(
    tool_call: dict,
    tools: dict[str, Any],
    session_id: str,
) -> str:
    """Executes a single tool call and returns the string result."""
    tool_name = tool_call["name"]
    tool_input = tool_call["input"]
    bound_tool = tools.get(tool_name)

    if bound_tool is None:
        logger.warning("Session %s: tool %r not found in registry", session_id, tool_name)
        return f"[Error]: Tool '{tool_name}' is not available."

    logger.debug("Session %s: executing tool %r with %r", session_id, tool_name, tool_input)
    try:
        result = await bound_tool(**tool_input)
        return str(result)
    except Exception as exc:
        logger.exception("Session %s: tool %r raised exception", session_id, tool_name)
        return f"[Tool Error]: {exc}"


def _try_parse_structured(content: str, schema: type) -> Any | None:
    """Attempts to parse JSON from content into the given Pydantic schema."""
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    raw = json_match.group(1) if json_match else content.strip()

    try:
        data = json.loads(raw)
        return schema(**data)
    except (json.JSONDecodeError, Exception):
        pass

    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return schema(**data)
        except (json.JSONDecodeError, Exception):
            pass

    return None


def _make_result(
    outcome: SessionOutcome,
    steps: int,
    tool_calls: int,
    usage: TokenUsage,
    messages: list[dict],
    start_ms: int,
    error: str | None = None,
    structured_output: Any | None = None,
) -> SessionResult:
    return SessionResult(
        outcome=outcome,
        steps_executed=steps,
        tool_call_count=tool_calls,
        usage=usage,
        messages=messages,
        error=error,
        structured_output=structured_output,
        duration_ms=int(time.time() * 1000) - start_ms,
    )


def _add_usage(total: TokenUsage, delta: TokenUsage) -> None:
    total.input_tokens += delta.input_tokens
    total.output_tokens += delta.output_tokens
    total.cache_read_tokens += delta.cache_read_tokens
    total.cache_write_tokens += delta.cache_write_tokens


class _StepResult:
    __slots__ = ("assistant_content", "finish_reason", "structured_output", "tool_calls", "usage")

    def __init__(
        self,
        assistant_content: str | None,
        tool_calls: list[dict] | None,
        usage: TokenUsage | None,
        finish_reason: str | None,
        structured_output: Any | None,
    ) -> None:
        self.assistant_content = assistant_content
        self.tool_calls = tool_calls
        self.usage = usage
        self.finish_reason = finish_reason
        self.structured_output = structured_output
