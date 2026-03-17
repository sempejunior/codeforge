from __future__ import annotations

from codeforge.domain.entities.plan import (
    ImplementationPlan,
    Phase,
    PhaseType,
    Subtask,
    SubtaskStatus,
    WorkflowType,
)
from codeforge.domain.services.subtask_dependency_resolver import (
    get_ready_subtasks,
    resolve_execution_order,
)


def make_plan(*phases: Phase) -> ImplementationPlan:
    return ImplementationPlan(
        feature="test",
        workflow_type=WorkflowType.MODIFICATION,
        phases=list(phases),
    )


def test_single_phase_no_deps_all_ready():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.IMPLEMENTATION,
            subtasks=[
                Subtask(id="1.1", title="A", description=""),
                Subtask(id="1.2", title="B", description=""),
            ],
        )
    )
    ready = get_ready_subtasks(plan, stuck_ids=set())
    assert set(ready) == {"1.1", "1.2"}


def test_intra_phase_dep_only_first_ready():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.IMPLEMENTATION,
            subtasks=[
                Subtask(id="1.1", title="A", description=""),
                Subtask(id="1.2", title="B", description="", depends_on=["1.1"]),
            ],
        )
    )
    ready = get_ready_subtasks(plan, stuck_ids=set())
    assert ready == ["1.1"]


def test_second_phase_blocked_by_incomplete_first():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.SETUP,
            subtasks=[Subtask(id="1.1", title="A", description="")],
        ),
        Phase(
            number=2,
            name="P2",
            phase_type=PhaseType.IMPLEMENTATION,
            depends_on=[1],
            subtasks=[Subtask(id="2.1", title="B", description="")],
        ),
    )
    ready = get_ready_subtasks(plan, stuck_ids=set())
    assert ready == ["1.1"]


def test_second_phase_unblocked_after_first_complete():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.SETUP,
            subtasks=[
                Subtask(id="1.1", title="A", description="", status=SubtaskStatus.COMPLETED)
            ],
        ),
        Phase(
            number=2,
            name="P2",
            phase_type=PhaseType.IMPLEMENTATION,
            depends_on=[1],
            subtasks=[Subtask(id="2.1", title="B", description="")],
        ),
    )
    ready = get_ready_subtasks(plan, stuck_ids=set())
    assert ready == ["2.1"]


def test_stuck_subtasks_excluded():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.IMPLEMENTATION,
            subtasks=[
                Subtask(id="1.1", title="A", description=""),
                Subtask(id="1.2", title="B", description=""),
            ],
        )
    )
    ready = get_ready_subtasks(plan, stuck_ids={"1.1"})
    assert ready == ["1.2"]


def test_resolve_order_no_deps_single_batch():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.IMPLEMENTATION,
            subtasks=[
                Subtask(id="1.1", title="A", description=""),
                Subtask(id="1.2", title="B", description=""),
            ],
        )
    )
    order = resolve_execution_order(plan)
    assert len(order) == 1
    assert set(order[0]) == {"1.1", "1.2"}


def test_resolve_order_sequential_deps():
    plan = make_plan(
        Phase(
            number=1,
            name="P1",
            phase_type=PhaseType.IMPLEMENTATION,
            subtasks=[
                Subtask(id="1.1", title="A", description=""),
                Subtask(id="1.2", title="B", description="", depends_on=["1.1"]),
                Subtask(id="1.3", title="C", description="", depends_on=["1.2"]),
            ],
        )
    )
    order = resolve_execution_order(plan)
    assert len(order) == 3
    assert order[0] == ["1.1"]
    assert order[1] == ["1.2"]
    assert order[2] == ["1.3"]


def test_plan_get_next_pending_respects_deps(sample_plan):
    nxt = sample_plan.get_next_pending_subtask(stuck_ids=set())
    assert nxt is not None
    assert nxt.id == "1.1"


def test_plan_get_next_pending_after_first_complete(sample_plan):
    sample_plan.mark_subtask_completed("1.1")
    nxt = sample_plan.get_next_pending_subtask(stuck_ids=set())
    assert nxt is not None
    assert nxt.id == "1.2"
