from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum

from ..events.base import DomainEvent
from ..events.sprint_events import (
    SprintCompleted,
    SprintCreated,
    SprintStarted,
    SprintStatusChanged,
)
from ..value_objects.sprint_id import SprintId
from ..value_objects.story_id import StoryId


class SprintStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


VALID_SPRINT_TRANSITIONS: dict[SprintStatus, frozenset[SprintStatus]] = {
    SprintStatus.PLANNED: frozenset({SprintStatus.ACTIVE, SprintStatus.CANCELLED}),
    SprintStatus.ACTIVE: frozenset({SprintStatus.COMPLETED, SprintStatus.CANCELLED}),
    SprintStatus.COMPLETED: frozenset(),
    SprintStatus.CANCELLED: frozenset(),
}


@dataclass
class SprintMetrics:
    tasks_done: int = 0
    tasks_total: int = 0
    stories_done: int = 0
    stories_total: int = 0

    @property
    def completion_pct(self) -> float:
        if self.tasks_total == 0:
            return 0.0
        return self.tasks_done / self.tasks_total


@dataclass
class Sprint:
    id: SprintId
    name: str
    start_date: date
    end_date: date
    story_ids: list[StoryId]
    status: SprintStatus = SprintStatus.PLANNED
    metrics: SprintMetrics = field(default_factory=SprintMetrics)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition_to(self, new_status: SprintStatus) -> list[DomainEvent]:
        allowed = VALID_SPRINT_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition: {self.status!r} -> {new_status!r}")
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        return [
            SprintStatusChanged(
                sprint_id=str(self.id), old_status=old_status, new_status=new_status
            )
        ]

    def start(self) -> list[DomainEvent]:
        events = self.transition_to(SprintStatus.ACTIVE)
        events.append(SprintStarted(sprint_id=str(self.id)))
        return events

    def complete(self) -> list[DomainEvent]:
        events = self.transition_to(SprintStatus.COMPLETED)
        events.append(
            SprintCompleted(
                sprint_id=str(self.id),
                stories_done=self.metrics.stories_done,
                stories_total=self.metrics.stories_total,
            )
        )
        return events

    def cancel(self) -> list[DomainEvent]:
        return self.transition_to(SprintStatus.CANCELLED)

    def add_story(self, story_id: StoryId) -> None:
        if story_id not in self.story_ids:
            self.story_ids.append(story_id)
            self.updated_at = datetime.now(UTC)

    def remove_story(self, story_id: StoryId) -> None:
        if story_id in self.story_ids:
            self.story_ids.remove(story_id)
            self.updated_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        name: str,
        start_date: date,
        end_date: date,
        story_ids: list[StoryId] | None = None,
    ) -> tuple[Sprint, list[DomainEvent]]:
        sprint_id = SprintId.generate()
        sprint = cls(
            id=sprint_id,
            name=name,
            start_date=start_date,
            end_date=end_date,
            story_ids=story_ids or [],
        )
        events: list[DomainEvent] = [SprintCreated(sprint_id=str(sprint_id), name=name)]
        return sprint, events
