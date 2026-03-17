from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from codeforge.application.dto.agent_session_dto import SessionResult
from codeforge.application.use_cases.execute_subtasks import (
    _build_subtask_prompt,
    _get_ready_batch,
    execute_subtasks,
)
from codeforge.domain.entities.agent import SessionOutcome, TokenUsage
from codeforge.domain.entities.plan import (
    ImplementationPlan,
    Phase,
    PhaseType,
    Subtask,
    SubtaskStatus,
    WorkflowType,
)
from codeforge.domain.value_objects.model_id import ModelId


def _model() -> ModelId:
    return ModelId("anthropic:claude-sonnet-4-20250514")


def _make_plan(*subtask_titles: str, depends_on: dict[str, list[str]] | None = None) -> ImplementationPlan:
    depends_on = depends_on or {}
    subtasks = [
        Subtask(
            id=f"st-{i}",
            title=title,
            description=f"Implement {title}",
            depends_on=depends_on.get(f"st-{i}", []),
        )
        for i, title in enumerate(subtask_titles)
    ]
    phase = Phase(number=1, name="Main", phase_type=PhaseType.IMPLEMENTATION, subtasks=subtasks)
    return ImplementationPlan(
        feature="test feature",
        workflow_type=WorkflowType.MODIFICATION,
        phases=[phase],
    )


def _ok_result() -> SessionResult:
    return SessionResult(
        outcome=SessionOutcome.COMPLETED,
        usage=TokenUsage(input_tokens=50, output_tokens=20),
    )


def _fail_result() -> SessionResult:
    return SessionResult(outcome=SessionOutcome.ERROR, usage=TokenUsage())


def _rate_limit_result() -> SessionResult:
    return SessionResult(outcome=SessionOutcome.RATE_LIMITED, usage=TokenUsage())


# ── _get_ready_batch ──────────────────────────────────────────────────────────


def test_get_ready_batch_returns_all_independent_subtasks():
    plan = _make_plan("A", "B", "C")
    batch = _get_ready_batch(plan, stuck_ids=set(), max_size=3)
    assert len(batch) == 3


def test_get_ready_batch_respects_max_size():
    plan = _make_plan("A", "B", "C")
    batch = _get_ready_batch(plan, stuck_ids=set(), max_size=2)
    assert len(batch) == 2


def test_get_ready_batch_skips_stuck():
    plan = _make_plan("A", "B")
    batch = _get_ready_batch(plan, stuck_ids={"st-0"}, max_size=3)
    assert len(batch) == 1
    assert batch[0].id == "st-1"


def test_get_ready_batch_does_not_include_same_subtask_twice():
    plan = _make_plan("A")
    batch = _get_ready_batch(plan, stuck_ids=set(), max_size=3)
    assert len(batch) == 1  # only 1 subtask exists


def test_get_ready_batch_respects_dependencies():
    plan = _make_plan("A", "B", depends_on={"st-1": ["st-0"]})
    batch = _get_ready_batch(plan, stuck_ids=set(), max_size=3)
    # st-1 depends on st-0, which is PENDING (not COMPLETED), so only st-0 is ready
    assert len(batch) == 1
    assert batch[0].id == "st-0"


# ── _build_subtask_prompt ─────────────────────────────────────────────────────


def test_build_subtask_prompt_includes_title():
    st = Subtask(id="1", title="Add login", description="Implement login endpoint")
    prompt = _build_subtask_prompt(st)
    assert "Add login" in prompt


def test_build_subtask_prompt_includes_files():
    st = Subtask(
        id="1",
        title="Add login",
        description="desc",
        files_to_create=["auth.py"],
        files_to_modify=["routes.py"],
    )
    prompt = _build_subtask_prompt(st)
    assert "auth.py" in prompt
    assert "routes.py" in prompt


def test_build_subtask_prompt_includes_acceptance_criteria():
    st = Subtask(
        id="1",
        title="t",
        description="d",
        acceptance_criteria=["Returns 200 on valid login"],
    )
    prompt = _build_subtask_prompt(st)
    assert "Returns 200 on valid login" in prompt


# ── execute_subtasks ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_executes_single_subtask(tmp_path: Path):
    plan = _make_plan("Implement feature")

    async def mock_session(config, provider):
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t1",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 1
    assert result.stuck_count == 0
    assert result.success is True


@pytest.mark.asyncio
async def test_executes_multiple_independent_subtasks(tmp_path: Path):
    plan = _make_plan("A", "B", "C")

    async def mock_session(config, provider):
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t2",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 3
    assert result.stuck_count == 0


@pytest.mark.asyncio
async def test_subtask_marked_stuck_after_max_retries(tmp_path: Path):
    plan = _make_plan("Failing subtask")

    async def mock_session(config, provider):
        return _fail_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t3",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 0
    assert result.stuck_count == 1
    subtask = plan.phases[0].subtasks[0]
    assert subtask.status == SubtaskStatus.STUCK


@pytest.mark.asyncio
async def test_subtask_retries_before_giving_up(tmp_path: Path):
    plan = _make_plan("Flaky subtask")
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return _fail_result()
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t4",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 1
    assert call_count == 3


@pytest.mark.asyncio
async def test_rate_limit_resets_attempt_count(tmp_path: Path):
    plan = _make_plan("Rate-limited subtask")
    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _rate_limit_result()
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t5",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 1
    # Rate limit didn't count as an attempt
    subtask = plan.phases[0].subtasks[0]
    assert subtask.attempt_count == 1  # only the successful attempt counts


@pytest.mark.asyncio
async def test_cancelled_returns_early(tmp_path: Path):
    plan = _make_plan("A", "B", "C")
    event = asyncio.Event()
    event.set()

    call_count = 0

    async def mock_session(config, provider):
        nonlocal call_count
        call_count += 1
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t6",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
            abort_event=event,
        )

    assert result.error == "Cancelled"
    assert call_count == 0


@pytest.mark.asyncio
async def test_dependent_subtasks_execute_in_order(tmp_path: Path):
    plan = _make_plan("A", "B", depends_on={"st-1": ["st-0"]})
    execution_order: list[str] = []

    async def mock_session(config, provider):
        # Extract subtask id from session_id pattern "task_id-subtask-{subtask_id}"
        subtask_id = config.session_id.split("-subtask-")[-1]
        execution_order.append(subtask_id)
        return _ok_result()

    with (
        patch(
            "codeforge.application.use_cases.execute_subtasks.run_continuable_session",
            side_effect=mock_session,
        ),
        patch("codeforge.application.use_cases.execute_subtasks.asyncio.sleep"),
    ):
        result = await execute_subtasks(
            plan=plan,
            task_id="t7",
            model=_model(),
            provider=None,
            tools={},
            project_path=tmp_path,
        )

    assert result.completed_count == 2
    assert execution_order[0] == "st-0"
    assert execution_order[1] == "st-1"
