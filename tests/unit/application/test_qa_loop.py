from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from codeforge.application.dto.agent_session_dto import SessionResult
from codeforge.application.use_cases.run_qa_loop import _parse_qa_report, run_qa_loop
from codeforge.domain.entities.agent import SessionOutcome, TokenUsage
from codeforge.domain.entities.qa_report import IssueSeverity, QAVerdict
from codeforge.domain.value_objects.model_id import ModelId


def _model() -> ModelId:
    return ModelId("anthropic:claude-sonnet-4-20250514")


def _ok_result() -> SessionResult:
    return SessionResult(
        outcome=SessionOutcome.COMPLETED,
        tool_call_count=1,
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    )


def _failed_result(outcome: SessionOutcome) -> SessionResult:
    return SessionResult(outcome=outcome, usage=TokenUsage())


def _write_qa_report(path: Path, verdict: str, issues: list[dict] | None = None) -> None:
    data = {
        "verdict": verdict,
        "tests_passed": verdict == "approved",
        "build_passed": True,
        "issues": issues or [],
        "notes": "",
    }
    (path / "qa_report.md").write_text(f"```json\n{json.dumps(data)}\n```")


# ── _parse_qa_report ──────────────────────────────────────────────────────────


def test_parse_qa_report_missing_file_returns_unknown(tmp_path: Path):
    report = _parse_qa_report(tmp_path, iteration=1)
    assert report.verdict == QAVerdict.UNKNOWN


def test_parse_qa_report_approved(tmp_path: Path):
    _write_qa_report(tmp_path, "approved")
    report = _parse_qa_report(tmp_path, iteration=1)
    assert report.verdict == QAVerdict.APPROVED
    assert report.tests_passed is True


def test_parse_qa_report_rejected_with_issues(tmp_path: Path):
    issues = [
        {"title": "Null check missing", "severity": "critical", "description": "NPE possible"}
    ]
    _write_qa_report(tmp_path, "rejected", issues)
    report = _parse_qa_report(tmp_path, iteration=1)
    assert report.verdict == QAVerdict.REJECTED
    assert len(report.issues) == 1
    assert report.issues[0].severity == IssueSeverity.CRITICAL


def test_parse_qa_report_infers_verdict_from_text(tmp_path: Path):
    (tmp_path / "qa_report.md").write_text("The code looks good. approved!")
    report = _parse_qa_report(tmp_path, iteration=1)
    assert report.verdict == QAVerdict.APPROVED


def test_parse_qa_report_iteration_stored(tmp_path: Path):
    _write_qa_report(tmp_path, "approved")
    report = _parse_qa_report(tmp_path, iteration=3)
    assert report.iteration == 3


# ── run_qa_loop ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approved_on_first_cycle(tmp_path: Path):
    _write_qa_report(tmp_path, "approved")

    async def mock_session(config, provider):
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t1",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.cycles == 1
    assert result.qa_report is not None
    assert result.qa_report.verdict == QAVerdict.APPROVED


@pytest.mark.asyncio
async def test_rejected_then_approved_after_fix(tmp_path: Path):
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        # cycle 1 reviewer → rejected; cycle 1 fixer → ok; cycle 2 reviewer → approved
        if call_count == 1:
            _write_qa_report(tmp_path, "rejected")
        elif call_count == 3:
            _write_qa_report(tmp_path, "approved")
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t2",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert call_count == 3  # reviewer, fixer, reviewer
    assert result.cycles == 2


@pytest.mark.asyncio
async def test_max_cycles_without_approval_returns_failure(tmp_path: Path):
    _write_qa_report(tmp_path, "rejected")

    async def mock_session(config, provider):
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t3",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
            max_cycles=2,
        )

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_recurring_issues_escalates_to_failure(tmp_path: Path):
    recurring_issue = {
        "title": "Null pointer exception",
        "severity": "critical",
        "description": "Always fails",
    }

    async def mock_session(config, provider):
        _write_qa_report(tmp_path, "rejected", [recurring_issue])
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t4",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
            max_cycles=3,
        )

    assert result.success is False
    assert "Recurring" in (result.error or "")


@pytest.mark.asyncio
async def test_cancelled_before_first_cycle(tmp_path: Path):
    event = asyncio.Event()
    event.set()

    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t5",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
            abort_event=event,
        )

    assert result.success is False
    assert result.error == "Cancelled"
    assert call_count == 0


@pytest.mark.asyncio
async def test_reviewer_provider_failure_returns_error(tmp_path: Path):
    async def mock_session(config, provider):
        return _failed_result(SessionOutcome.AUTH_FAILURE)

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t6",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is False
    assert "AUTH_FAILURE" in (result.error or "").upper() or "failed" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_usage_accumulated_across_cycles(tmp_path: Path):
    _write_qa_report(tmp_path, "approved")

    async def mock_session(config, provider):
        return SessionResult(
            outcome=SessionOutcome.COMPLETED,
            tool_call_count=1,
            usage=TokenUsage(input_tokens=300, output_tokens=100),
        )

    with patch(
        "codeforge.application.use_cases.run_qa_loop.run_continuable_session",
        side_effect=mock_session,
    ):
        result = await run_qa_loop(
            task_id="t7",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.total_usage.input_tokens == 300
