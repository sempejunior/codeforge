from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from pathlib import Path

from codeforge.application.dto.agent_session_dto import SessionConfig
from codeforge.application.dto.pipeline_dto import QALoopResult
from codeforge.application.services.prompt_builder import build_system_prompt
from codeforge.application.use_cases.run_continuable_session import run_continuable_session
from codeforge.domain.entities.agent import AgentType, SessionOutcome, TokenUsage
from codeforge.domain.entities.qa_report import IssueSeverity, QAIssue, QAReport, QAVerdict
from codeforge.domain.ports.ai_provider import AIProviderPort
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.infrastructure.tools.base import BoundTool

logger = logging.getLogger(__name__)

_MAX_QA_CYCLES = 3

_REVIEWER_PROMPT = """\
## QA Review

Review the implementation against spec.md and implementation_plan.json.
Run all available tests. Check correctness, test coverage, code quality, and security.
Write your verdict to qa_report.md as JSON.
"""

_FIXER_PROMPT = """\
## QA Fix — Cycle {cycle}

Read qa_report.md for the list of issues. Fix all CRITICAL and MAJOR issues.
Run tests to verify fixes. Update qa_report.md with the results after fixing.
Do not introduce new features beyond what is needed to fix the issues.
"""


async def run_qa_loop(
    task_id: str,
    model: ModelId,
    provider: AIProviderPort,
    tools: dict[str, BoundTool],
    project_path: Path,
    abort_event: asyncio.Event | None = None,
    max_cycles: int = _MAX_QA_CYCLES,
) -> QALoopResult:
    """Runs the QA loop: reviewer → fixer, up to max_cycles times.

    Returns success when the reviewer approves. Returns failure on recurring issues
    or when max_cycles is exhausted without approval.
    """
    qa_history: list[QAReport] = []
    total_usage = TokenUsage()

    for cycle in range(1, max_cycles + 1):
        if abort_event and abort_event.is_set():
            return QALoopResult(
                success=False,
                qa_report=qa_history[-1] if qa_history else None,
                error="Cancelled",
                cycles=cycle - 1,
                total_usage=total_usage,
            )

        logger.info("QA loop: task=%s cycle=%d/%d (review)", task_id, cycle, max_cycles)

        reviewer_config = SessionConfig(
            agent_type=AgentType.QA_REVIEWER,
            model=model,
            system_prompt=build_system_prompt(AgentType.QA_REVIEWER, project_path),
            messages=[{"role": "user", "content": _REVIEWER_PROMPT}],
            tools=tools,
            task_id=task_id,
            session_id=f"{task_id}-qa-review-{cycle}",
            abort_event=abort_event,
        )

        reviewer_result = await run_continuable_session(reviewer_config, provider)
        _accumulate_usage(total_usage, reviewer_result.usage)

        if reviewer_result.outcome not in (SessionOutcome.COMPLETED, SessionOutcome.MAX_STEPS):
            return QALoopResult(
                success=False,
                qa_report=qa_history[-1] if qa_history else None,
                error=f"QA reviewer failed: {reviewer_result.outcome}",
                cycles=cycle,
                total_usage=total_usage,
            )

        qa_report = _parse_qa_report(project_path, iteration=cycle)

        if qa_report.has_recurring_issues(qa_history):
            logger.warning(
                "QA loop: task=%s recurring issues detected after cycle %d", task_id, cycle
            )
            return QALoopResult(
                success=False,
                qa_report=qa_report,
                error="Recurring QA issues — escalating to failure",
                cycles=cycle,
                total_usage=total_usage,
            )

        qa_history.append(qa_report)

        if qa_report.verdict == QAVerdict.APPROVED:
            logger.info("QA loop: task=%s approved at cycle %d", task_id, cycle)
            return QALoopResult(
                success=True,
                qa_report=qa_report,
                cycles=cycle,
                total_usage=total_usage,
            )

        if cycle == max_cycles:
            break

        logger.info("QA loop: task=%s rejected at cycle %d, running fixer", task_id, cycle)

        fixer_config = SessionConfig(
            agent_type=AgentType.QA_FIXER,
            model=model,
            system_prompt=build_system_prompt(AgentType.QA_FIXER, project_path),
            messages=[{"role": "user", "content": _FIXER_PROMPT.format(cycle=cycle)}],
            tools=tools,
            task_id=task_id,
            session_id=f"{task_id}-qa-fix-{cycle}",
            abort_event=abort_event,
        )

        fixer_result = await run_continuable_session(fixer_config, provider)
        _accumulate_usage(total_usage, fixer_result.usage)

        if fixer_result.outcome not in (SessionOutcome.COMPLETED, SessionOutcome.MAX_STEPS):
            return QALoopResult(
                success=False,
                qa_report=qa_history[-1],
                error=f"QA fixer failed: {fixer_result.outcome}",
                cycles=cycle,
                total_usage=total_usage,
            )

    last_report = qa_history[-1] if qa_history else None
    return QALoopResult(
        success=False,
        qa_report=last_report,
        error=f"QA loop failed after {max_cycles} cycles without approval",
        cycles=max_cycles,
        total_usage=total_usage,
    )


def _parse_qa_report(project_path: Path, iteration: int) -> QAReport:
    """Reads and parses qa_report.md from the project directory."""
    qa_file = project_path / "qa_report.md"

    if not qa_file.exists():
        return QAReport(verdict=QAVerdict.UNKNOWN, iteration=iteration)

    content = qa_file.read_text()

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    raw_json = json_match.group(1) if json_match else None

    if raw_json is None:
        obj_match = re.search(r"\{.*\}", content, re.DOTALL)
        raw_json = obj_match.group(0) if obj_match else None

    if raw_json is None:
        verdict = QAVerdict.APPROVED if "approved" in content.lower() else QAVerdict.REJECTED
        return QAReport(verdict=verdict, iteration=iteration, notes=content[:500])

    try:
        data = json.loads(raw_json)
        return _build_report_from_dict(data, iteration)
    except json.JSONDecodeError:
        verdict = QAVerdict.APPROVED if "approved" in content.lower() else QAVerdict.REJECTED
        return QAReport(verdict=verdict, iteration=iteration, notes=content[:500])


def _build_report_from_dict(data: dict, iteration: int) -> QAReport:
    issues: list[QAIssue] = []
    for item in data.get("issues", []):
        with contextlib.suppress(ValueError, KeyError):
            issues.append(
                QAIssue(
                    title=str(item.get("title", "Unknown issue")),
                    severity=IssueSeverity(item.get("severity", "minor")),
                    description=str(item.get("description", "")),
                    file_path=item.get("file_path"),
                    suggested_fix=item.get("suggested_fix"),
                )
            )

    verdict_str = str(data.get("verdict", "unknown")).lower()
    try:
        verdict = QAVerdict(verdict_str)
    except ValueError:
        verdict = QAVerdict.UNKNOWN

    return QAReport(
        verdict=verdict,
        issues=issues,
        iteration=iteration,
        tests_passed=bool(data.get("tests_passed", False)),
        build_passed=bool(data.get("build_passed", False)),
        notes=str(data.get("notes", "")),
    )


def _accumulate_usage(total: TokenUsage, delta: TokenUsage) -> None:
    total.input_tokens += delta.input_tokens
    total.output_tokens += delta.output_tokens
    total.cache_read_tokens += delta.cache_read_tokens
    total.cache_write_tokens += delta.cache_write_tokens
