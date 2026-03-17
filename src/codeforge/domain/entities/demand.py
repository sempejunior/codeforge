from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..events.base import DomainEvent
from ..events.demand_events import (
    DemandBreakdownCompleted,
    DemandBreakdownRequested,
    DemandCreated,
    DemandStatusChanged,
)
from ..value_objects.demand_id import DemandId
from ..value_objects.project_id import ProjectId


class DemandStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    BREAKDOWN_PENDING = "breakdown_pending"
    BREAKDOWN_COMPLETE = "breakdown_complete"
    IN_SPRINT = "in_sprint"
    DONE = "done"
    CANCELLED = "cancelled"


VALID_DEMAND_TRANSITIONS: dict[DemandStatus, frozenset[DemandStatus]] = {
    DemandStatus.DRAFT: frozenset({DemandStatus.ACTIVE, DemandStatus.CANCELLED}),
    DemandStatus.ACTIVE: frozenset({
        DemandStatus.BREAKDOWN_PENDING, DemandStatus.CANCELLED
    }),
    DemandStatus.BREAKDOWN_PENDING: frozenset({
        DemandStatus.BREAKDOWN_COMPLETE, DemandStatus.CANCELLED
    }),
    DemandStatus.BREAKDOWN_COMPLETE: frozenset({
        DemandStatus.IN_SPRINT, DemandStatus.ACTIVE, DemandStatus.CANCELLED
    }),
    DemandStatus.IN_SPRINT: frozenset({DemandStatus.DONE, DemandStatus.CANCELLED}),
    DemandStatus.DONE: frozenset(),
    DemandStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class LinkedProject:
    project_id: ProjectId
    base_branch: str = "main"


@dataclass
class Demand:
    id: DemandId
    title: str
    business_objective: str
    acceptance_criteria: list[str]
    linked_projects: list[LinkedProject]
    status: DemandStatus = DemandStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: DemandStatus) -> list[DomainEvent]:
        allowed = VALID_DEMAND_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition: {self.status!r} -> {new_status!r}")
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        return [
            DemandStatusChanged(
                demand_id=str(self.id), old_status=old_status, new_status=new_status
            )
        ]

    def request_breakdown(self) -> list[DomainEvent]:
        events = self.transition_to(DemandStatus.BREAKDOWN_PENDING)
        events.append(DemandBreakdownRequested(demand_id=str(self.id)))
        return events

    def complete_breakdown(self, total_tasks: int) -> list[DomainEvent]:
        events = self.transition_to(DemandStatus.BREAKDOWN_COMPLETE)
        events.append(
            DemandBreakdownCompleted(demand_id=str(self.id), total_tasks=total_tasks)
        )
        return events

    def activate(self) -> list[DomainEvent]:
        return self.transition_to(DemandStatus.ACTIVE)

    def cancel(self) -> list[DomainEvent]:
        return self.transition_to(DemandStatus.CANCELLED)

    @classmethod
    def create(
        cls,
        title: str,
        business_objective: str,
        acceptance_criteria: list[str] | None = None,
        linked_projects: list[LinkedProject] | None = None,
    ) -> tuple[Demand, list[DomainEvent]]:
        demand_id = DemandId.generate()
        demand = cls(
            id=demand_id,
            title=title,
            business_objective=business_objective,
            acceptance_criteria=acceptance_criteria or [],
            linked_projects=linked_projects or [],
        )
        events: list[DomainEvent] = [
            DemandCreated(demand_id=str(demand_id), title=title)
        ]
        return demand, events
