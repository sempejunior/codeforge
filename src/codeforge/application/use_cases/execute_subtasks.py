from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.dto.pipeline_dto import SubtaskExecutionResult
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_continuable_session import run_continuable_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.plan import ImplementationPlan, Subtask, SubtaskStatus
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import BoundTool

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 3
_STAGGER_DELAY_S = 1.0
_RATE_LIMIT_BASE_BACKOFF_S = 30.0
_MAX_BACKOFF_S = 300.0


async def execute_subtasks(
    plan: ImplementationPlan,
    task_id: str,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None = None,
) -> SubtaskExecutionResult:
    """Executes all pending subtasks respecting dependencies, up to 3 concurrently.

    On rate limit: exponential backoff, subtask reset for retry (not counted against retries).
    On other failure: retry up to subtask.max_retries, then mark stuck.
    """
    stuck_ids: set[str] = set()
    total_usage = TokenUsage()
    rate_limit_streak = 0

    while not plan.all_subtasks_done():
        if abort_event and abort_event.is_set():
            return SubtaskExecutionResult(
                completed_count=plan.completed_subtasks(),
                stuck_count=len(stuck_ids),
                total_usage=total_usage,
                error="Cancelled",
            )

        batch = _get_ready_batch(plan, stuck_ids, _MAX_CONCURRENT)
        if not batch:
            break

        for subtask in batch:
            subtask.mark_in_progress()

        tasks: list[asyncio.Task] = []
        for i, subtask in enumerate(batch):
            if i > 0:
                await asyncio.sleep(_STAGGER_DELAY_S)
            tasks.append(
                asyncio.create_task(
                    _execute_subtask(
                        subtask, task_id, model, provider, tools, project_path, abort_event
                    )
                )
            )

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        any_rate_limited = False
        for subtask, raw in zip(batch, raw_results, strict=False):
            if isinstance(raw, BaseException):
                logger.exception("Subtask %s raised: %s", subtask.id, raw)
                subtask.mark_failed()
                if subtask.can_retry():
                    subtask.status = SubtaskStatus.PENDING
                else:
                    subtask.mark_stuck()
                    stuck_ids.add(subtask.id)
                continue

            outcome, usage = raw
            _accumulate_usage(total_usage, usage)

            if outcome == SessionOutcome.RATE_LIMITED:
                any_rate_limited = True
                subtask.mark_failed()
                subtask.status = SubtaskStatus.PENDING
                subtask.attempt_count -= 1
                logger.warning("Subtask %s: rate limited, will retry after backoff", subtask.id)
                continue

            if outcome == SessionOutcome.COMPLETED:
                plan.mark_subtask_completed(subtask.id)
                rate_limit_streak = 0
                logger.info("Subtask %s completed", subtask.id)
            else:
                subtask.mark_failed()
                logger.warning("Subtask %s failed: outcome=%s", subtask.id, outcome)
                if subtask.can_retry():
                    subtask.status = SubtaskStatus.PENDING
                else:
                    subtask.mark_stuck()
                    stuck_ids.add(subtask.id)

        if any_rate_limited:
            backoff = min(_RATE_LIMIT_BASE_BACKOFF_S * (2**rate_limit_streak), _MAX_BACKOFF_S)
            rate_limit_streak += 1
            logger.info("Rate limited, backing off %.0fs (streak=%d)", backoff, rate_limit_streak)
            await asyncio.sleep(backoff)

    return SubtaskExecutionResult(
        completed_count=plan.completed_subtasks(),
        stuck_count=len(stuck_ids),
        total_usage=total_usage,
    )


def _get_ready_batch(
    plan: ImplementationPlan,
    stuck_ids: set[str],
    max_size: int,
) -> list[Subtask]:
    """Returns up to max_size subtasks that are ready (all deps satisfied)."""
    batch: list[Subtask] = []
    already_batched: set[str] = set()

    while len(batch) < max_size:
        subtask = plan.get_next_pending_subtask(stuck_ids | already_batched)
        if subtask is None:
            break
        already_batched.add(subtask.id)
        batch.append(subtask)

    return batch


async def _execute_subtask(
    subtask: Subtask,
    task_id: str,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None,
) -> tuple[SessionOutcome, TokenUsage]:
    prompt = _build_subtask_prompt(subtask)

    config = SessionConfig(
        agent_type=AgentType.CODER,
        model=model,
        system_prompt=build_system_prompt(AgentType.CODER, project_path),
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        task_id=task_id,
        session_id=f"{task_id}-subtask-{subtask.id}",
        abort_event=abort_event,
    )

    result = await run_continuable_session(config, provider)
    return result.outcome, result.usage


def _build_subtask_prompt(subtask: Subtask) -> str:
    parts = [
        f"## Subtask: {subtask.title}",
        f"**ID:** {subtask.id}",
        f"\n{subtask.description}",
    ]

    if subtask.acceptance_criteria:
        criteria = "\n".join(f"- {c}" for c in subtask.acceptance_criteria)
        parts.append(f"\n**Acceptance Criteria:**\n{criteria}")

    if subtask.files_to_create:
        files = "\n".join(f"- {f}" for f in subtask.files_to_create)
        parts.append(f"\n**Files to create:**\n{files}")

    if subtask.files_to_modify:
        files = "\n".join(f"- {f}" for f in subtask.files_to_modify)
        parts.append(f"\n**Files to modify:**\n{files}")

    return "\n".join(parts)


def _accumulate_usage(total: TokenUsage, delta: TokenUsage) -> None:
    total.input_tokens += delta.input_tokens
    total.output_tokens += delta.output_tokens
    total.cache_read_tokens += delta.cache_read_tokens
    total.cache_write_tokens += delta.cache_write_tokens
