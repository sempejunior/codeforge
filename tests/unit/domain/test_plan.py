from __future__ import annotations

from codeforge.domain.entities.plan import (
    ImplementationPlan,
    Phase,
    PhaseType,
    Subtask,
    SubtaskStatus,
    WorkflowType,
)


def make_simple_plan() -> ImplementationPlan:
    return ImplementationPlan(
        feature="auth",
        workflow_type=WorkflowType.MODIFICATION,
        phases=[
            Phase(
                number=1,
                name="P1",
                phase_type=PhaseType.IMPLEMENTATION,
                subtasks=[
                    Subtask(id="1.1", title="A", description=""),
                    Subtask(id="1.2", title="B", description="", depends_on=["1.1"]),
                ],
            )
        ],
    )


def test_get_subtask_by_id():
    plan = make_simple_plan()
    subtask = plan.get_subtask("1.1")
    assert subtask is not None
    assert subtask.id == "1.1"


def test_get_subtask_missing_returns_none():
    plan = make_simple_plan()
    assert plan.get_subtask("99.99") is None


def test_mark_subtask_completed():
    plan = make_simple_plan()
    plan.mark_subtask_completed("1.1")
    assert plan.get_subtask("1.1").status == SubtaskStatus.COMPLETED


def test_all_subtasks_done_false_initially():
    plan = make_simple_plan()
    assert plan.all_subtasks_done() is False


def test_all_subtasks_done_true_when_all_complete():
    plan = make_simple_plan()
    plan.mark_subtask_completed("1.1")
    plan.mark_subtask_completed("1.2")
    assert plan.all_subtasks_done() is True


def test_total_and_completed_counts():
    plan = make_simple_plan()
    assert plan.total_subtasks() == 2
    assert plan.completed_subtasks() == 0
    plan.mark_subtask_completed("1.1")
    assert plan.completed_subtasks() == 1


def test_subtask_can_retry():
    s = Subtask(id="1.1", title="A", description="", max_retries=3, attempt_count=2)
    assert s.can_retry() is True


def test_subtask_cannot_retry_at_limit():
    s = Subtask(id="1.1", title="A", description="", max_retries=3, attempt_count=3)
    assert s.can_retry() is False


def test_phase_complete_when_all_done_or_stuck():
    phase = Phase(
        number=1,
        name="P",
        phase_type=PhaseType.SETUP,
        subtasks=[
            Subtask(id="1.1", title="A", description="", status=SubtaskStatus.COMPLETED),
            Subtask(id="1.2", title="B", description="", status=SubtaskStatus.STUCK),
        ],
    )
    assert phase.is_complete() is True
