from __future__ import annotations

import pytest

from codeforge.domain.entities.task import Task, TaskSource, TaskStatus
from codeforge.domain.events.task_events import (
    TaskCompleted,
    TaskCreated,
    TaskFailed,
    TaskStarted,
    TaskStatusChanged,
)
from codeforge.domain.value_objects.project_id import ProjectId


def test_task_create_returns_event(project_id):
    task, events = Task.create(project_id=project_id, title="Fix bug", description="desc")
    assert task.title == "Fix bug"
    assert task.status == TaskStatus.BACKLOG
    assert len(events) == 1
    assert isinstance(events[0], TaskCreated)


def test_start_pipeline_queues_task(sample_task):
    events = sample_task.start_pipeline()
    assert sample_task.status == TaskStatus.QUEUED
    assert any(isinstance(e, TaskStarted) for e in events)


def test_transition_valid(sample_task):
    sample_task.transition_to(TaskStatus.QUEUED)
    events = sample_task.transition_to(TaskStatus.SPEC_CREATION)
    assert sample_task.status == TaskStatus.SPEC_CREATION
    assert isinstance(events[0], TaskStatusChanged)


def test_transition_invalid_raises(sample_task):
    with pytest.raises(ValueError, match="Invalid transition"):
        sample_task.transition_to(TaskStatus.COMPLETED)


def test_mark_failed(sample_task):
    events = sample_task.mark_failed("something broke")
    assert sample_task.status == TaskStatus.FAILED
    assert sample_task.error_message == "something broke"
    assert any(isinstance(e, TaskFailed) for e in events)
    assert any(isinstance(e, TaskStatusChanged) for e in events)


def test_mark_completed(sample_task):
    sample_task.status = TaskStatus.QA_REVIEW
    events = sample_task.mark_completed()
    assert sample_task.status == TaskStatus.COMPLETED
    assert any(isinstance(e, TaskCompleted) for e in events)


def test_default_source_is_manual():
    pid = ProjectId.generate()
    task, _ = Task.create(project_id=pid, title="t", description="d")
    assert task.source == TaskSource.MANUAL


def test_source_ref_stored():
    pid = ProjectId.generate()
    task, _ = Task.create(
        project_id=pid,
        title="t",
        description="d",
        source=TaskSource.GITHUB_ISSUE,
        source_ref="owner/repo#42",
    )
    assert task.source_ref == "owner/repo#42"
