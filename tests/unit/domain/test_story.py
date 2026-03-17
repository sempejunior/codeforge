from __future__ import annotations

import pytest

from codeforge.domain.entities.story import Story, StoryStatus
from codeforge.domain.events.story_events import (
    StoryAddedToSprint,
    StoryCreated,
    StoryStatusChanged,
)
from codeforge.domain.value_objects.demand_id import DemandId
from codeforge.domain.value_objects.sprint_id import SprintId


@pytest.fixture
def demand_id() -> DemandId:
    return DemandId.generate()


def test_story_create_returns_event(demand_id):
    story, events = Story.create(
        demand_id=demand_id,
        title="Pagamento via PIX",
        description="Geração de QR Code e confirmação",
    )
    assert story.title == "Pagamento via PIX"
    assert story.status == StoryStatus.BACKLOG
    assert story.sprint_id is None
    assert len(events) == 1
    assert isinstance(events[0], StoryCreated)
    assert events[0].demand_id == str(demand_id)


def test_story_create_defaults_empty_criteria(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    assert story.acceptance_criteria == []


def test_story_add_to_sprint(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    sprint_id = SprintId.generate()
    events = story.add_to_sprint(sprint_id)
    assert story.status == StoryStatus.IN_SPRINT
    assert story.sprint_id == sprint_id
    assert any(isinstance(e, StoryAddedToSprint) for e in events)
    added = next(e for e in events if isinstance(e, StoryAddedToSprint))
    assert added.sprint_id == str(sprint_id)


def test_story_mark_in_progress(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    story.add_to_sprint(SprintId.generate())
    events = story.mark_in_progress()
    assert story.status == StoryStatus.IN_PROGRESS
    assert any(isinstance(e, StoryStatusChanged) for e in events)


def test_story_mark_done(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    story.add_to_sprint(SprintId.generate())
    story.mark_in_progress()
    events = story.mark_done()
    assert story.status == StoryStatus.DONE
    assert any(isinstance(e, StoryStatusChanged) for e in events)


def test_story_cancel(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    events = story.cancel()
    assert story.status == StoryStatus.CANCELLED
    assert any(isinstance(e, StoryStatusChanged) for e in events)


def test_story_invalid_transition_raises(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    with pytest.raises(ValueError, match="Invalid transition"):
        story.mark_in_progress()


def test_story_cancel_from_terminal_raises(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    story.cancel()
    with pytest.raises(ValueError, match="Invalid transition"):
        story.cancel()


def test_story_breakdown_flow(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    story.transition_to(StoryStatus.BREAKDOWN_PENDING)
    story.transition_to(StoryStatus.BREAKDOWN_COMPLETE)
    assert story.status == StoryStatus.BREAKDOWN_COMPLETE


def test_story_breakdown_complete_back_to_backlog(demand_id):
    story, _ = Story.create(demand_id=demand_id, title="t", description="d")
    story.transition_to(StoryStatus.BREAKDOWN_PENDING)
    story.transition_to(StoryStatus.BREAKDOWN_COMPLETE)
    story.transition_to(StoryStatus.BACKLOG)
    assert story.status == StoryStatus.BACKLOG
