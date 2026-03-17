from __future__ import annotations

import pytest

from codeforge.domain.entities.demand import (
    Demand,
    DemandStatus,
    LinkedProject,
)
from codeforge.domain.events.demand_events import (
    DemandBreakdownCompleted,
    DemandBreakdownRequested,
    DemandCreated,
    DemandStatusChanged,
)
from codeforge.domain.value_objects.project_id import ProjectId


def test_demand_create_returns_event():
    demand, events = Demand.create(
        title="Checkout com PIX",
        business_objective="Permitir pagamentos via PIX no e-commerce",
    )
    assert demand.title == "Checkout com PIX"
    assert demand.status == DemandStatus.DRAFT
    assert len(events) == 1
    assert isinstance(events[0], DemandCreated)
    assert events[0].title == "Checkout com PIX"


def test_demand_create_with_acceptance_criteria():
    demand, _ = Demand.create(
        title="t",
        business_objective="o",
        acceptance_criteria=["AC1", "AC2"],
    )
    assert demand.acceptance_criteria == ["AC1", "AC2"]


def test_demand_create_defaults_empty_lists():
    demand, _ = Demand.create(title="t", business_objective="o")
    assert demand.acceptance_criteria == []
    assert demand.linked_projects == []


def test_demand_activate():
    demand, _ = Demand.create(title="t", business_objective="o")
    events = demand.activate()
    assert demand.status == DemandStatus.ACTIVE
    assert any(isinstance(e, DemandStatusChanged) for e in events)


def test_demand_request_breakdown():
    demand, _ = Demand.create(title="t", business_objective="o")
    demand.activate()
    events = demand.request_breakdown()
    assert demand.status == DemandStatus.BREAKDOWN_PENDING
    assert any(isinstance(e, DemandBreakdownRequested) for e in events)
    assert any(isinstance(e, DemandStatusChanged) for e in events)


def test_demand_complete_breakdown():
    demand, _ = Demand.create(title="t", business_objective="o")
    demand.activate()
    demand.request_breakdown()
    events = demand.complete_breakdown(total_tasks=5)
    assert demand.status == DemandStatus.BREAKDOWN_COMPLETE
    completed_events = [e for e in events if isinstance(e, DemandBreakdownCompleted)]
    assert len(completed_events) == 1
    assert completed_events[0].total_tasks == 5


def test_demand_cancel_from_draft():
    demand, _ = Demand.create(title="t", business_objective="o")
    events = demand.cancel()
    assert demand.status == DemandStatus.CANCELLED
    assert any(isinstance(e, DemandStatusChanged) for e in events)


def test_demand_invalid_transition_raises():
    demand, _ = Demand.create(title="t", business_objective="o")
    with pytest.raises(ValueError, match="Invalid transition"):
        demand.request_breakdown()


def test_demand_cancel_from_terminal_raises():
    demand, _ = Demand.create(title="t", business_objective="o")
    demand.cancel()
    with pytest.raises(ValueError, match="Invalid transition"):
        demand.cancel()


def test_linked_project_frozen():
    pid = ProjectId.generate()
    lp = LinkedProject(project_id=pid, base_branch="main")
    assert lp.project_id == pid
    assert lp.base_branch == "main"


def test_demand_with_linked_projects():
    pid = ProjectId.generate()
    lp = LinkedProject(project_id=pid, base_branch="develop")
    demand, _ = Demand.create(
        title="t",
        business_objective="o",
        linked_projects=[lp],
    )
    assert len(demand.linked_projects) == 1
    assert demand.linked_projects[0].base_branch == "develop"
