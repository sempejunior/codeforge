from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.dto.pipeline_dto import BuildPipelineResult
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.execute_subtasks import execute_subtasks
from codeforge.application.use_cases.run_continuable_session import run_continuable_session
from codeforge.application.use_cases.run_qa_loop import run_qa_loop
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.plan import (
    ImplementationPlan,
    Phase,
    PhaseType,
    Subtask,
    WorkflowType,
)
from codeforge.domain.entities.spec import Spec
from codeforge.domain.ports.ai_provider import AIProviderPort, Message
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import BoundTool

logger = logging.getLogger(__name__)

_MAX_PLAN_ATTEMPTS = 3
_REPAIR_MODEL = ModelId("anthropic:claude-haiku-4-5-20251001")
_REPAIR_MAX_INPUT_CHARS = 10_000

_REPAIR_SYSTEM = (
    "You are a JSON repair assistant. "
    "The following is an invalid or incomplete implementation plan JSON. "
    "Return ONLY the corrected JSON — no explanation, no markdown fences. "
    "Ensure the output has 'feature', 'workflow_type', 'phases', and 'final_acceptance' keys."
)

_PLANNING_PROMPT = """\
## Planning Task

Read spec.md and explore the existing codebase. Then create implementation_plan.json
with a detailed, phased implementation plan.

The plan must be valid JSON matching the schema in your system prompt.
Keep each subtask small and focused — a coder should complete it in < 30 minutes.
Write the plan to implementation_plan.json.
"""


async def run_build_pipeline(
    task_id: str,
    spec: Spec,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None = None,
) -> BuildPipelineResult:
    """Runs the full build pipeline: planning → coding → QA loop."""
    total_usage = TokenUsage()

    # Phase 1: Planning
    logger.info("Build pipeline: task=%s phase=planning", task_id)
    plan_result = await _run_planning(task_id, model, provider, tools, project_path, abort_event)
    _accumulate_usage(total_usage, plan_result.usage)

    if plan_result.plan is None:
        return BuildPipelineResult(
            success=False,
            error=plan_result.error or "Planning failed",
            total_usage=total_usage,
        )

    plan = plan_result.plan

    # Phase 2: Coding
    logger.info(
        "Build pipeline: task=%s phase=coding total_subtasks=%d",
        task_id,
        plan.total_subtasks(),
    )
    coding_result = await execute_subtasks(
        plan=plan,
        task_id=task_id,
        model=model,
        provider=provider,
        tools=tools,
        project_path=project_path,
        abort_event=abort_event,
    )
    _accumulate_usage(total_usage, coding_result.total_usage)

    if coding_result.error == "Cancelled":
        return BuildPipelineResult(
            success=False,
            plan=plan,
            error="Cancelled during coding",
            total_usage=total_usage,
        )

    # Phase 3: QA Loop
    logger.info(
        "Build pipeline: task=%s phase=qa completed=%d stuck=%d",
        task_id,
        coding_result.completed_count,
        coding_result.stuck_count,
    )
    qa_result = await run_qa_loop(
        task_id=task_id,
        model=model,
        provider=provider,
        tools=tools,
        project_path=project_path,
        abort_event=abort_event,
    )
    _accumulate_usage(total_usage, qa_result.total_usage)

    return BuildPipelineResult(
        success=qa_result.success,
        plan=plan,
        qa_report=qa_result.qa_report,
        error=qa_result.error if not qa_result.success else None,
        total_usage=total_usage,
    )


async def _run_planning(
    task_id: str,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None,
) -> _PlanResult:
    for attempt in range(_MAX_PLAN_ATTEMPTS):
        config = SessionConfig(
            agent_type=AgentType.PLANNER,
            model=model,
            system_prompt=build_system_prompt(AgentType.PLANNER, project_path),
            messages=[{"role": "user", "content": _PLANNING_PROMPT}],
            tools=tools,
            task_id=task_id,
            session_id=f"{task_id}-planning-{attempt}",
            abort_event=abort_event,
        )

        result = await run_continuable_session(config, provider)

        if result.outcome not in (SessionOutcome.COMPLETED, SessionOutcome.MAX_STEPS):
            return _PlanResult(
                plan=None,
                usage=result.usage,
                error=f"Planner session failed: {result.outcome}",
            )

        plan_file = project_path / "implementation_plan.json"
        raw_json = plan_file.read_text() if plan_file.exists() else None

        if raw_json is None:
            raw_json = _extract_json_from_messages(result.messages)

        plan = _try_parse_plan(raw_json)
        if plan is not None:
            return _PlanResult(plan=plan, usage=result.usage)

        if raw_json:
            logger.warning("Planning attempt %d: invalid JSON, attempting repair", attempt)
            repaired = await _repair_plan_json(raw_json, provider)
            plan = _try_parse_plan(repaired)
            if plan is not None:
                return _PlanResult(plan=plan, usage=result.usage)

        if attempt < _MAX_PLAN_ATTEMPTS - 1:
            logger.warning("Planning attempt %d: could not parse plan, retrying", attempt)

    return _PlanResult(
        plan=None,
        usage=TokenUsage(),
        error=f"Planning failed after {_MAX_PLAN_ATTEMPTS} attempts",
    )


def _try_parse_plan(raw: str | None) -> ImplementationPlan | None:
    if not raw:
        return None

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    try:
        data = json.loads(raw)
        return _build_plan_from_dict(data)
    except json.JSONDecodeError:
        pass

    obj_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if obj_match:
        try:
            data = json.loads(obj_match.group(0))
            return _build_plan_from_dict(data)
        except json.JSONDecodeError:
            pass

    return None


def _build_plan_from_dict(data: dict) -> ImplementationPlan | None:
    try:
        workflow_str = data.get("workflow_type", "modification")
        try:
            workflow_type = WorkflowType(workflow_str)
        except ValueError:
            workflow_type = WorkflowType.MODIFICATION

        phases: list[Phase] = []
        for phase_data in data.get("phases", []):
            subtasks: list[Subtask] = []
            for st_data in phase_data.get("subtasks", []):
                subtasks.append(
                    Subtask(
                        id=str(st_data.get("id", uuid.uuid4())),
                        title=str(st_data.get("title", "")),
                        description=str(st_data.get("description", "")),
                        files_to_modify=list(st_data.get("files_to_modify", [])),
                        files_to_create=list(st_data.get("files_to_create", [])),
                        acceptance_criteria=list(st_data.get("acceptance_criteria", [])),
                        depends_on=[str(d) for d in st_data.get("depends_on", [])],
                    )
                )

            phase_type_str = phase_data.get("phase_type", "implementation")
            try:
                phase_type = PhaseType(phase_type_str)
            except ValueError:
                phase_type = PhaseType.IMPLEMENTATION

            phases.append(
                Phase(
                    number=int(phase_data.get("number", len(phases) + 1)),
                    name=str(phase_data.get("name", "")),
                    phase_type=phase_type,
                    subtasks=subtasks,
                    depends_on=[int(d) for d in phase_data.get("depends_on", [])],
                )
            )

        return ImplementationPlan(
            feature=str(data.get("feature", "")),
            workflow_type=workflow_type,
            phases=phases,
            final_acceptance=list(data.get("final_acceptance", [])),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _extract_json_from_messages(messages: list[dict]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                return json_match.group(1)
            obj_match = re.search(r"\{.*\}", content, re.DOTALL)
            if obj_match:
                return obj_match.group(0)
    return None


async def _repair_plan_json(raw: str, provider: AIProviderPort) -> str:
    try:
        result = await provider.generate(
            model=_REPAIR_MODEL,
            system=_REPAIR_SYSTEM,
            messages=[Message(role="user", content=raw[:_REPAIR_MAX_INPUT_CHARS])],
        )
        return result.content
    except Exception:
        logger.exception("Plan JSON repair failed")
        return raw


def _accumulate_usage(total: TokenUsage, delta: TokenUsage) -> None:
    total.input_tokens += delta.input_tokens
    total.output_tokens += delta.output_tokens
    total.cache_read_tokens += delta.cache_read_tokens
    total.cache_write_tokens += delta.cache_write_tokens


class _PlanResult:
    __slots__ = ("error", "plan", "usage")

    def __init__(
        self,
        plan: ImplementationPlan | None,
        usage: TokenUsage,
        error: str | None = None,
    ) -> None:
        self.plan = plan
        self.usage = usage
        self.error = error
