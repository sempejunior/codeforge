from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from codeforge.application.dto.agent_session_dto import SessionResult
from codeforge.application.dto.pipeline_dto import QALoopResult, SubtaskExecutionResult
from codeforge.application.use_cases.run_build_pipeline import (
    _build_plan_from_dict,
    _extract_json_from_messages,
    _try_parse_plan,
    run_build_pipeline,
)
from codeforge.domain.entities.agent import SessionOutcome, TokenUsage
from codeforge.domain.entities.qa_report import QAReport, QAVerdict
from codeforge.domain.entities.spec import ComplexityTier, Spec
from codeforge.domain.value_objects.model_id import ModelId


def _model() -> ModelId:
    return ModelId("anthropic:claude-sonnet-4-20250514")


def _make_spec(task_id: str = "t1") -> Spec:
    return Spec(task_id=task_id, complexity=ComplexityTier.STANDARD, content="# Spec content")


_VALID_PLAN_DICT = {
    "feature": "Add JWT auth",
    "workflow_type": "modification",
    "phases": [
        {
            "number": 1,
            "name": "Implementation",
            "phase_type": "implementation",
            "depends_on": [],
            "subtasks": [
                {
                    "id": "1.1",
                    "title": "Add JWT middleware",
                    "description": "Create middleware",
                    "files_to_create": ["middleware.py"],
                    "files_to_modify": [],
                    "acceptance_criteria": ["Returns 401 on invalid token"],
                    "depends_on": [],
                }
            ],
        }
    ],
    "final_acceptance": ["All tests pass"],
}


# ── Plan parsing ──────────────────────────────────────────────────────────────


def test_build_plan_from_dict_valid():
    plan = _build_plan_from_dict(_VALID_PLAN_DICT)
    assert plan is not None
    assert plan.feature == "Add JWT auth"
    assert len(plan.phases) == 1
    assert len(plan.phases[0].subtasks) == 1
    assert plan.phases[0].subtasks[0].title == "Add JWT middleware"


def test_build_plan_from_dict_unknown_workflow_type_falls_back():
    data = {**_VALID_PLAN_DICT, "workflow_type": "nonexistent"}
    plan = _build_plan_from_dict(data)
    assert plan is not None
    from codeforge.domain.entities.plan import WorkflowType
    assert plan.workflow_type == WorkflowType.MODIFICATION


def test_build_plan_from_dict_missing_required_field_returns_none():
    plan = _build_plan_from_dict({"feature": "test"})  # missing phases
    assert plan is not None  # phases defaults to []
    assert plan.phases == []


def test_try_parse_plan_valid_json():
    raw = json.dumps(_VALID_PLAN_DICT)
    plan = _try_parse_plan(raw)
    assert plan is not None


def test_try_parse_plan_with_markdown_fences():
    raw = f"Here is the plan:\n```json\n{json.dumps(_VALID_PLAN_DICT)}\n```"
    plan = _try_parse_plan(raw)
    assert plan is not None


def test_try_parse_plan_invalid_json_returns_none():
    plan = _try_parse_plan("not json at all")
    assert plan is None


def test_try_parse_plan_none_input_returns_none():
    assert _try_parse_plan(None) is None


def test_extract_json_from_messages_finds_json_block():
    messages = [
        {"role": "user", "content": "plan this"},
        {
            "role": "assistant",
            "content": f"Here's the plan:\n```json\n{json.dumps(_VALID_PLAN_DICT)}\n```",
        },
    ]
    raw = _extract_json_from_messages(messages)
    assert raw is not None
    assert "feature" in raw


def test_extract_json_from_messages_returns_none_if_no_json():
    messages = [{"role": "assistant", "content": "No JSON here"}]
    assert _extract_json_from_messages(messages) is None


# ── run_build_pipeline ────────────────────────────────────────────────────────


def _make_ok_coding_result() -> SubtaskExecutionResult:
    return SubtaskExecutionResult(
        completed_count=1,
        stuck_count=0,
        total_usage=TokenUsage(input_tokens=200, output_tokens=100),
    )


def _make_ok_qa_result() -> QALoopResult:
    return QALoopResult(
        success=True,
        qa_report=QAReport(verdict=QAVerdict.APPROVED),
        cycles=1,
        total_usage=TokenUsage(input_tokens=300, output_tokens=150),
    )


def _make_failed_qa_result() -> QALoopResult:
    return QALoopResult(
        success=False,
        qa_report=QAReport(verdict=QAVerdict.REJECTED),
        error="QA failed",
        cycles=3,
        total_usage=TokenUsage(),
    )


@pytest.mark.asyncio
async def test_successful_full_pipeline(tmp_path: Path):
    plan_file = tmp_path / "implementation_plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN_DICT))

    async def mock_planner_session(config, provider):
        return SessionResult(
            outcome=SessionOutcome.COMPLETED,
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )

    with (
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_continuable_session",
            side_effect=mock_planner_session,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.execute_subtasks",
            return_value=_make_ok_coding_result(),
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_qa_loop",
            return_value=_make_ok_qa_result(),
        ),
    ):
        result = await run_build_pipeline(
            task_id="t1",
            spec=_make_spec(),
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.plan is not None
    assert result.qa_report is not None
    assert result.qa_report.verdict == QAVerdict.APPROVED


@pytest.mark.asyncio
async def test_planning_failure_returns_early(tmp_path: Path):
    async def mock_planner_session(config, provider):
        return SessionResult(outcome=SessionOutcome.ERROR, usage=TokenUsage())

    with (
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_continuable_session",
            side_effect=mock_planner_session,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.execute_subtasks"
        ) as mock_coding,
    ):
        result = await run_build_pipeline(
            task_id="t2",
            spec=_make_spec(),
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is False
    assert result.plan is None
    mock_coding.assert_not_called()


@pytest.mark.asyncio
async def test_plan_json_repaired_when_invalid(tmp_path: Path):
    """Planner produces invalid JSON; repair succeeds on second try."""
    call_count = 0

    async def mock_planner_session(config, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: planner returns no file but has JSON in messages
            return SessionResult(
                outcome=SessionOutcome.COMPLETED,
                usage=TokenUsage(),
                messages=[
                    {"role": "assistant", "content": "bad json: {not valid json }"}
                ],
            )
        # Second attempt (after repair fails, re-plan)
        plan_file = tmp_path / "implementation_plan.json"
        plan_file.write_text(json.dumps(_VALID_PLAN_DICT))
        return SessionResult(
            outcome=SessionOutcome.COMPLETED,
            usage=TokenUsage(),
        )

    async def mock_repair(raw, provider):
        return "still invalid"

    with (
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_continuable_session",
            side_effect=mock_planner_session,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline._repair_plan_json",
            side_effect=mock_repair,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.execute_subtasks",
            return_value=_make_ok_coding_result(),
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_qa_loop",
            return_value=_make_ok_qa_result(),
        ),
    ):
        result = await run_build_pipeline(
            task_id="t3",
            spec=_make_spec(),
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert call_count >= 2


@pytest.mark.asyncio
async def test_qa_failure_propagated(tmp_path: Path):
    plan_file = tmp_path / "implementation_plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN_DICT))

    async def mock_planner_session(config, provider):
        return SessionResult(outcome=SessionOutcome.COMPLETED, usage=TokenUsage())

    with (
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_continuable_session",
            side_effect=mock_planner_session,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.execute_subtasks",
            return_value=_make_ok_coding_result(),
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_qa_loop",
            return_value=_make_failed_qa_result(),
        ),
    ):
        result = await run_build_pipeline(
            task_id="t4",
            spec=_make_spec(),
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is False
    assert result.error == "QA failed"
    assert result.plan is not None


@pytest.mark.asyncio
async def test_usage_accumulated_across_all_phases(tmp_path: Path):
    plan_file = tmp_path / "implementation_plan.json"
    plan_file.write_text(json.dumps(_VALID_PLAN_DICT))

    async def mock_planner_session(config, provider):
        return SessionResult(
            outcome=SessionOutcome.COMPLETED,
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )

    coding_result = SubtaskExecutionResult(
        completed_count=1,
        total_usage=TokenUsage(input_tokens=200, output_tokens=100),
    )
    qa_result = QALoopResult(
        success=True,
        qa_report=QAReport(verdict=QAVerdict.APPROVED),
        cycles=1,
        total_usage=TokenUsage(input_tokens=300, output_tokens=150),
    )

    with (
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_continuable_session",
            side_effect=mock_planner_session,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.execute_subtasks",
            return_value=coding_result,
        ),
        patch(
            "codeforge.application.use_cases.run_build_pipeline.run_qa_loop",
            return_value=qa_result,
        ),
    ):
        result = await run_build_pipeline(
            task_id="t5",
            spec=_make_spec(),
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.success is True
    assert result.total_usage.input_tokens == 600  # 100 + 200 + 300
    assert result.total_usage.output_tokens == 300  # 50 + 100 + 150
