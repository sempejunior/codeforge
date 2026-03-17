from __future__ import annotations

import logging

from codeforge.application.dto.agent_session_dto import SessionConfig, SessionResult
from codeforge.domain.entities.agent import SessionOutcome, TokenUsage
from codeforge.domain.ports.ai_provider import AIProviderPort, Message

from .run_agent_session import _add_usage, run_agent_session

logger = logging.getLogger(__name__)

_MAX_CONTINUATIONS = 5
_SUMMARY_MAX_CHARS = 30_000
_RAW_FALLBACK_CHARS = 3_000

_SUMMARIZER_SYSTEM = (
    "You are a concise session summarizer. "
    "Summarize what was accomplished, files modified, decisions made, "
    "and what remains to be done. Be concrete. Target ~800 words."
)

_CONTINUATION_TEMPLATE = """\
## Session Continuation ({n})

You are continuing a previous session that ran out of context window space.
Here is a summary of your prior work:

{summary}

Continue where you left off. Do NOT repeat completed work. Focus on what remains.
"""


async def run_continuable_session(
    config: SessionConfig,
    provider: AIProviderPort,
    max_continuations: int = _MAX_CONTINUATIONS,
) -> SessionResult:
    """Wraps run_agent_session with automatic context window continuation.

    When a session hits context_window outcome, summarizes the conversation
    and starts a new session with the summary as context.
    """
    current_config = config
    total_usage = TokenUsage()
    total_steps = 0
    total_tool_calls = 0
    total_duration_ms = 0
    continuation_count = 0

    for i in range(max_continuations + 1):
        result = await run_agent_session(current_config, provider)

        total_steps += result.steps_executed
        total_tool_calls += result.tool_call_count
        total_duration_ms += result.duration_ms
        _add_usage(total_usage, result.usage)

        if result.outcome != SessionOutcome.CONTEXT_WINDOW:
            return SessionResult(
                outcome=result.outcome,
                steps_executed=total_steps,
                tool_call_count=total_tool_calls,
                usage=total_usage,
                messages=result.messages,
                structured_output=result.structured_output,
                error=result.error,
                duration_ms=total_duration_ms,
                continuation_count=continuation_count,
            )

        if i >= max_continuations:
            logger.warning(
                "Session %s: max continuations (%d) reached, treating as completed.",
                config.session_id,
                max_continuations,
            )
            return SessionResult(
                outcome=SessionOutcome.COMPLETED,
                steps_executed=total_steps,
                tool_call_count=total_tool_calls,
                usage=total_usage,
                messages=result.messages,
                duration_ms=total_duration_ms,
                continuation_count=continuation_count,
            )

        if current_config.abort_event and current_config.abort_event.is_set():
            return SessionResult(
                outcome=SessionOutcome.CANCELLED,
                steps_executed=total_steps,
                tool_call_count=total_tool_calls,
                usage=total_usage,
                messages=result.messages,
                duration_ms=total_duration_ms,
                continuation_count=continuation_count,
            )

        continuation_count += 1
        logger.info(
            "Session %s: context overflow, starting continuation %d.",
            config.session_id,
            continuation_count,
        )

        summary = await _compact_messages(result.messages, provider, current_config)
        continuation_msg = _CONTINUATION_TEMPLATE.format(n=continuation_count, summary=summary)

        current_config = SessionConfig(
            agent_type=config.agent_type,
            model=config.model,
            system_prompt=config.system_prompt,
            messages=[{"role": "user", "content": continuation_msg}],
            tools=config.tools,
            max_steps=config.max_steps,
            context_window_limit=config.context_window_limit,
            thinking_level=config.thinking_level,
            output_schema=config.output_schema,
            abort_event=config.abort_event,
            task_id=config.task_id,
            session_id=config.session_id,
        )

    return SessionResult(
        outcome=SessionOutcome.COMPLETED,
        steps_executed=total_steps,
        tool_call_count=total_tool_calls,
        usage=total_usage,
        duration_ms=total_duration_ms,
        continuation_count=continuation_count,
    )


async def _compact_messages(
    messages: list[dict],
    provider: AIProviderPort,
    config: SessionConfig,
) -> str:
    """Summarizes the session messages into a compact string."""
    serialized = _serialize_messages(messages)
    if len(serialized) > _SUMMARY_MAX_CHARS:
        serialized = serialized[:_SUMMARY_MAX_CHARS] + "\n\n[... truncated ...]"

    try:
        from codeforge.domain.value_objects.model_id import ModelId

        summarizer_model = ModelId("anthropic:claude-haiku-4-5-20251001")
        result = await provider.generate(
            model=summarizer_model,
            system=_SUMMARIZER_SYSTEM,
            messages=[Message(role="user", content=serialized)],
        )
        return result.content
    except Exception:
        logger.exception("Failed to summarize session, using raw truncation.")
        return _raw_truncation(messages)


def _serialize_messages(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "unknown").upper()
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in content
            )
        parts.append(f"[{role}]\n{content}")
    return "\n\n---\n\n".join(parts)


def _raw_truncation(messages: list[dict]) -> str:
    last_five = messages[-5:]
    serialized = _serialize_messages(last_five)
    if len(serialized) > _RAW_FALLBACK_CHARS:
        serialized = serialized[:_RAW_FALLBACK_CHARS] + "\n\n[truncated]"
    return serialized
