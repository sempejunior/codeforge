from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..events.base import DomainEvent
from ..events.story_events import StoryAddedToSprint, StoryCreated, StoryStatusChanged
from ..value_objects.demand_id import DemandId
from ..value_objects.sprint_id import SprintId
from ..value_objects.story_id import StoryId


class StoryStatus(StrEnum):
    BACKLOG = "backlog"
    BREAKDOWN_PENDING = "breakdown_pending"
    BREAKDOWN_COMPLETE = "breakdown_complete"
    IN_SPRINT = "in_sprint"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


VALID_STORY_TRANSITIONS: dict[StoryStatus, frozenset[StoryStatus]] = {
    StoryStatus.BACKLOG: frozenset({
        StoryStatus.BREAKDOWN_PENDING, StoryStatus.IN_SPRINT, StoryStatus.CANCELLED
    }),
    StoryStatus.BREAKDOWN_PENDING: frozenset({
        StoryStatus.BREAKDOWN_COMPLETE, StoryStatus.CANCELLED
    }),
    StoryStatus.BREAKDOWN_COMPLETE: frozenset({
        StoryStatus.IN_SPRINT, StoryStatus.BACKLOG, StoryStatus.CANCELLED
    }),
    StoryStatus.IN_SPRINT: frozenset({
        StoryStatus.IN_PROGRESS, StoryStatus.CANCELLED
    }),
    StoryStatus.IN_PROGRESS: frozenset({StoryStatus.DONE, StoryStatus.CANCELLED}),
    StoryStatus.DONE: frozenset(),
    StoryStatus.CANCELLED: frozenset(),
}


@dataclass
class Story:
    id: StoryId
    demand_id: DemandId
    title: str
    description: str
    acceptance_criteria: list[str]
    sprint_id: SprintId | None = None
    status: StoryStatus = StoryStatus.BACKLOG
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: StoryStatus) -> list[DomainEvent]:
        allowed = VALID_STORY_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition: {self.status!r} -> {new_status!r}")
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        return [
            StoryStatusChanged(
                story_id=str(self.id), old_status=old_status, new_status=new_status
            )
        ]

    def add_to_sprint(self, sprint_id: SprintId) -> list[DomainEvent]:
        self.sprint_id = sprint_id
        events = self.transition_to(StoryStatus.IN_SPRINT)
        events.append(StoryAddedToSprint(story_id=str(self.id), sprint_id=str(sprint_id)))
        return events

    def mark_in_progress(self) -> list[DomainEvent]:
        return self.transition_to(StoryStatus.IN_PROGRESS)

    def mark_done(self) -> list[DomainEvent]:
        return self.transition_to(StoryStatus.DONE)

    def cancel(self) -> list[DomainEvent]:
        return self.transition_to(StoryStatus.CANCELLED)

    @classmethod
    def create(
        cls,
        demand_id: DemandId,
        title: str,
        description: str,
        acceptance_criteria: list[str] | None = None,
    ) -> tuple[Story, list[DomainEvent]]:
        story_id = StoryId.generate()
        story = cls(
            id=story_id,
            demand_id=demand_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria or [],
        )
        events: list[DomainEvent] = [
            StoryCreated(
                story_id=str(story_id), demand_id=str(demand_id), title=title
            )
        ]
        return story, events
