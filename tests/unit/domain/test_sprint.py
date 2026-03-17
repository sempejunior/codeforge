from __future__ import annotations

from datetime import date

import pytest

from codeforge.domain.entities.sprint import Sprint, SprintStatus
from codeforge.domain.events.sprint_events import (
    SprintCompleted,
    SprintCreated,
    SprintStarted,
    SprintStatusChanged,
)
from codeforge.domain.value_objects.story_id import StoryId


def test_sprint_create_returns_event():
    sprint, events = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    assert sprint.name == "Sprint 1"
    assert sprint.status == SprintStatus.PLANNED
    assert sprint.story_ids == []
    assert len(events) == 1
    assert isinstance(events[0], SprintCreated)
    assert events[0].name == "Sprint 1"


def test_sprint_create_with_stories():
    sid = StoryId.generate()
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
        story_ids=[sid],
    )
    assert sid in sprint.story_ids


def test_sprint_start():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    events = sprint.start()
    assert sprint.status == SprintStatus.ACTIVE
    assert any(isinstance(e, SprintStarted) for e in events)
    assert any(isinstance(e, SprintStatusChanged) for e in events)


def test_sprint_complete():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    sprint.start()
    sprint.metrics.stories_done = 3
    sprint.metrics.stories_total = 4
    events = sprint.complete()
    assert sprint.status == SprintStatus.COMPLETED
    completed = next(e for e in events if isinstance(e, SprintCompleted))
    assert completed.stories_done == 3
    assert completed.stories_total == 4


def test_sprint_cancel_from_planned():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    events = sprint.cancel()
    assert sprint.status == SprintStatus.CANCELLED
    assert any(isinstance(e, SprintStatusChanged) for e in events)


def test_sprint_invalid_transition_raises():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    with pytest.raises(ValueError, match="Invalid transition"):
        sprint.complete()


def test_sprint_complete_from_terminal_raises():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    sprint.start()
    sprint.complete()
    with pytest.raises(ValueError, match="Invalid transition"):
        sprint.complete()


def test_sprint_add_story():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    sid = StoryId.generate()
    sprint.add_story(sid)
    assert sid in sprint.story_ids


def test_sprint_add_story_idempotent():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    sid = StoryId.generate()
    sprint.add_story(sid)
    sprint.add_story(sid)
    assert sprint.story_ids.count(sid) == 1


def test_sprint_remove_story():
    sid = StoryId.generate()
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
        story_ids=[sid],
    )
    sprint.remove_story(sid)
    assert sid not in sprint.story_ids


def test_sprint_metrics_completion_pct():
    sprint, _ = Sprint.create(
        name="Sprint 1",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
    )
    assert sprint.metrics.completion_pct == 0.0
    sprint.metrics.tasks_done = 3
    sprint.metrics.tasks_total = 4
    assert sprint.metrics.completion_pct == pytest.approx(0.75)
