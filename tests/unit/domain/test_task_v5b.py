from __future__ import annotations

import pytest

from codeforge.domain.entities.task import AssigneeType, Task, TaskStatus
from codeforge.domain.events.task_events import (
    TaskApproved,
    TaskAwaitingHumanReview,
    TaskCodeReviewStarted,
)
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.story_id import StoryId


@pytest.fixture
def project_id() -> ProjectId:
    return ProjectId.generate()


def test_task_create_with_story_id(project_id):
    story_id = StoryId.generate()
    task, _ = Task.create(
        project_id=project_id,
        title="t",
        description="d",
        story_id=story_id,
    )
    assert task.story_id == story_id


def test_task_create_without_story_id(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    assert task.story_id is None


def test_task_default_assignee_is_unassigned(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    assert task.assignee_type == AssigneeType.UNASSIGNED


def test_task_assign_to_ai(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.assign_to(AssigneeType.AI)
    assert task.assignee_type == AssigneeType.AI


def test_task_assign_to_human(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.assign_to(AssigneeType.HUMAN)
    assert task.assignee_type == AssigneeType.HUMAN


def test_task_start_code_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.status = TaskStatus.QA_REVIEW
    events = task.start_code_review()
    assert task.status == TaskStatus.CODE_REVIEW
    assert any(isinstance(e, TaskCodeReviewStarted) for e in events)


def test_task_await_human_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.status = TaskStatus.CODE_REVIEW
    events = task.await_human_review()
    assert task.status == TaskStatus.AWAITING_REVIEW
    assert any(isinstance(e, TaskAwaitingHumanReview) for e in events)


def test_task_approve_from_code_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.status = TaskStatus.CODE_REVIEW
    events = task.approve(reviewer="ai")
    assert task.status == TaskStatus.COMPLETED
    assert any(isinstance(e, TaskApproved) for e in events)
    approved = next(e for e in events if isinstance(e, TaskApproved))
    assert approved.reviewer == "ai"


def test_task_approve_from_awaiting_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.status = TaskStatus.AWAITING_REVIEW
    events = task.approve(reviewer="john")
    assert task.status == TaskStatus.COMPLETED
    assert any(isinstance(e, TaskApproved) for e in events)


def test_task_code_review_invalid_from_backlog(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    with pytest.raises(ValueError, match="Invalid transition"):
        task.start_code_review()


def test_task_qa_review_can_go_to_code_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.status = TaskStatus.QA_REVIEW
    task.start_code_review()
    assert task.status == TaskStatus.CODE_REVIEW


def test_full_ai_pipeline_with_code_review(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.assign_to(AssigneeType.AI)
    task.start_pipeline()
    task.transition_to(TaskStatus.SPEC_CREATION)
    task.transition_to(TaskStatus.PLANNING)
    task.transition_to(TaskStatus.CODING)
    task.transition_to(TaskStatus.QA_REVIEW)
    task.start_code_review()
    task.approve(reviewer="ai")
    assert task.status == TaskStatus.COMPLETED
    assert task.assignee_type == AssigneeType.AI


def test_full_human_review_pipeline(project_id):
    task, _ = Task.create(project_id=project_id, title="t", description="d")
    task.assign_to(AssigneeType.AI)
    task.start_pipeline()
    task.transition_to(TaskStatus.SPEC_CREATION)
    task.transition_to(TaskStatus.PLANNING)
    task.transition_to(TaskStatus.CODING)
    task.transition_to(TaskStatus.QA_REVIEW)
    task.start_code_review()
    task.await_human_review()
    task.approve(reviewer="dev_carlos")
    assert task.status == TaskStatus.COMPLETED
