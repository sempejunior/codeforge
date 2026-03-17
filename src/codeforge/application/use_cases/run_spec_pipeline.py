from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.dto.pipeline_dto import SpecPipelineResult
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_continuable_session import run_continuable_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.spec import ComplexityTier, Spec, SpecPhase
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import BoundTool

logger = logging.getLogger(__name__)

_MAX_PHASE_RETRIES = 2

_PHASE_SEQUENCES: dict[ComplexityTier, list[SpecPhase]] = {
    ComplexityTier.SIMPLE: [
        SpecPhase.WRITING,
        SpecPhase.VALIDATION,
    ],
    ComplexityTier.STANDARD: [
        SpecPhase.DISCOVERY,
        SpecPhase.REQUIREMENTS,
        SpecPhase.WRITING,
        SpecPhase.VALIDATION,
    ],
    ComplexityTier.COMPLEX: [
        SpecPhase.DISCOVERY,
        SpecPhase.REQUIREMENTS,
        SpecPhase.RESEARCH,
        SpecPhase.CONTEXT,
        SpecPhase.WRITING,
        SpecPhase.CRITIQUE,
        SpecPhase.VALIDATION,
    ],
}

_PHASE_AGENT_TYPES: dict[SpecPhase, AgentType] = {
    SpecPhase.DISCOVERY: AgentType.SPEC_WRITER,
    SpecPhase.REQUIREMENTS: AgentType.SPEC_WRITER,
    SpecPhase.RESEARCH: AgentType.SPEC_WRITER,
    SpecPhase.CONTEXT: AgentType.SPEC_WRITER,
    SpecPhase.WRITING: AgentType.SPEC_WRITER,
    SpecPhase.CRITIQUE: AgentType.SPEC_CRITIC,
    SpecPhase.VALIDATION: AgentType.SPEC_CRITIC,
}

_PHASE_INSTRUCTIONS: dict[SpecPhase, str] = {
    SpecPhase.DISCOVERY: (
        "## Phase: Discovery\n\n"
        "Explore the codebase to understand its current architecture, patterns, and what "
        "changes are needed for this task. Write your findings to discovery.md."
    ),
    SpecPhase.REQUIREMENTS: (
        "## Phase: Requirements\n\n"
        "Based on the discovery notes, define detailed technical requirements. "
        "Write to requirements.md."
    ),
    SpecPhase.RESEARCH: (
        "## Phase: Research\n\n"
        "Research relevant patterns, libraries, and best practices for this task using "
        "WebFetch and WebSearch. Write your findings to research.md."
    ),
    SpecPhase.CONTEXT: (
        "## Phase: Context\n\n"
        "Synthesize the discovery, requirements, and research into a unified context document. "
        "Write to context.md."
    ),
    SpecPhase.WRITING: (
        "## Phase: Spec Writing\n\n"
        "Write the complete technical specification to spec.md using all accumulated context. "
        "Be concrete, actionable, and include acceptance criteria."
    ),
    SpecPhase.CRITIQUE: (
        "## Phase: Critique\n\n"
        "Read spec.md critically. Identify gaps, ambiguities, missing edge cases, and incorrect "
        "assumptions. Edit spec.md directly to fix issues. Write your review summary to "
        "spec_review.md."
    ),
    SpecPhase.VALIDATION: (
        "## Phase: Validation\n\n"
        "Validate that spec.md is complete, correct, and actionable. Fix any remaining issues. "
        "Write final validation notes to spec_validation.md."
    ),
}

_FORCE_TOOL_USE_SUFFIX = (
    "\n\nIMPORTANT: You MUST use the available tools to complete this task. "
    "Do not just write text — actually read files and write output files using the tools."
)


async def run_spec_pipeline(
    task_id: str,
    task_description: str,
    complexity: ComplexityTier,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None = None,
) -> SpecPipelineResult:
    """Runs the spec pipeline for the given complexity tier.

    Executes 2, 4, or 7 phases depending on complexity. Each phase runs an agent
    session that produces output files. Accumulated context flows into subsequent phases.
    """
    phases = _PHASE_SEQUENCES[complexity]
    spec = Spec(task_id=task_id, complexity=complexity)
    total_usage = TokenUsage()
    accumulated_context: list[str] = []

    for phase in phases:
        if abort_event and abort_event.is_set():
            return SpecPipelineResult(
                success=False,
                spec=spec,
                error="Cancelled",
                total_usage=total_usage,
                phases_completed=len(spec.phases_completed),
            )

        logger.info("Spec pipeline: task=%s phase=%s", task_id, phase)

        phase_result = await _run_phase(
            phase=phase,
            task_id=task_id,
            task_description=task_description,
            model=model,
            provider=provider,
            tools=tools,
            project_path=project_path,
            accumulated_context=accumulated_context,
            abort_event=abort_event,
        )

        _accumulate_usage(total_usage, phase_result.usage)

        if not phase_result.success:
            return SpecPipelineResult(
                success=False,
                spec=spec,
                error=phase_result.error,
                total_usage=total_usage,
                phases_completed=len(spec.phases_completed),
            )

        spec.add_phase(phase)
        if phase_result.output_summary:
            accumulated_context.append(f"[{phase.upper()}]\n{phase_result.output_summary}")

    spec_file = project_path / "spec.md"
    if spec_file.exists():
        spec.content = spec_file.read_text()

    return SpecPipelineResult(
        success=True,
        spec=spec,
        total_usage=total_usage,
        phases_completed=len(spec.phases_completed),
    )


async def _run_phase(
    phase: SpecPhase,
    task_id: str,
    task_description: str,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    accumulated_context: list[str],
    abort_event: asyncio.Event | None,
) -> _PhaseResult:
    agent_type = _PHASE_AGENT_TYPES[phase]

    for attempt in range(_MAX_PHASE_RETRIES + 1):
        prompt = _build_phase_prompt(
            phase=phase,
            task_description=task_description,
            accumulated_context=accumulated_context,
            force_tool_use=attempt > 0,
        )

        config = SessionConfig(
            agent_type=agent_type,
            model=model,
            system_prompt=build_system_prompt(agent_type, project_path),
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            task_id=task_id,
            session_id=f"{task_id}-{phase}-{attempt}",
            abort_event=abort_event,
        )

        result = await run_continuable_session(config, provider)

        if result.outcome == SessionOutcome.COMPLETED:
            if result.tool_call_count == 0 and attempt < _MAX_PHASE_RETRIES:
                logger.warning(
                    "Spec phase %s attempt %d: no tool calls, retrying",
                    phase,
                    attempt,
                )
                continue
            return _PhaseResult(
                success=True,
                usage=result.usage,
                output_summary=_extract_last_assistant_text(result.messages),
            )

        if result.outcome in (SessionOutcome.CANCELLED,):
            return _PhaseResult(
                success=False,
                usage=result.usage,
                error="Cancelled",
            )

        if result.outcome in (SessionOutcome.RATE_LIMITED, SessionOutcome.AUTH_FAILURE):
            return _PhaseResult(
                success=False,
                usage=result.usage,
                error=f"Provider error in phase {phase}: {result.outcome}",
            )

        if attempt < _MAX_PHASE_RETRIES:
            logger.warning(
                "Spec phase %s attempt %d: outcome=%s, retrying",
                phase,
                attempt,
                result.outcome,
            )
            continue

        return _PhaseResult(
            success=False,
            usage=result.usage,
            error=f"Phase {phase} failed after {_MAX_PHASE_RETRIES + 1} attempts: {result.outcome}",
        )

    return _PhaseResult(
        success=False,
        usage=TokenUsage(),
        error=f"Phase {phase} exhausted retries",
    )


def _build_phase_prompt(
    phase: SpecPhase,
    task_description: str,
    accumulated_context: list[str],
    force_tool_use: bool,
) -> str:
    parts = [
        f"## Task\n\n{task_description}",
        _PHASE_INSTRUCTIONS[phase],
    ]

    if accumulated_context:
        context_block = "\n\n".join(accumulated_context)
        parts.append(f"## Prior Phase Outputs\n\n{context_block}")

    if force_tool_use:
        parts.append(_FORCE_TOOL_USE_SUFFIX)

    return "\n\n".join(parts)


def _extract_last_assistant_text(messages: list[dict]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content[:2000]
    return None


def _accumulate_usage(total: TokenUsage, delta: TokenUsage) -> None:
    total.input_tokens += delta.input_tokens
    total.output_tokens += delta.output_tokens
    total.cache_read_tokens += delta.cache_read_tokens
    total.cache_write_tokens += delta.cache_write_tokens


class _PhaseResult:
    __slots__ = ("error", "output_summary", "success", "usage")

    def __init__(
        self,
        success: bool,
        usage: TokenUsage,
        error: str | None = None,
        output_summary: str | None = None,
    ) -> None:
        self.success = success
        self.usage = usage
        self.error = error
        self.output_summary = output_summary
