from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from ..events.base import DomainEvent
from ..events.task_events import (
    TaskApproved,
    TaskAwaitingHumanReview,
    TaskCancelled,
    TaskCodeReviewStarted,
    TaskCompleted,
    TaskCreated,
    TaskFailed,
    TaskStarted,
    TaskStatusChanged,
)
from ..value_objects.complexity import ComplexityTier
from ..value_objects.project_id import ProjectId
from ..value_objects.story_id import StoryId
from ..value_objects.task_id import TaskId

if TYPE_CHECKING:
    from .plan import ImplementationPlan
    from .qa_report import QAReport
    from .spec import Spec


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    QUEUED = "queued"
    SPEC_CREATION = "spec_creation"
    PLANNING = "planning"
    CODING = "coding"
    QA_REVIEW = "qa_review"
    QA_FIXING = "qa_fixing"
    CODE_REVIEW = "code_review"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskSource(StrEnum):
    MANUAL = "manual"
    GITHUB_ISSUE = "github_issue"
    JIRA_EPIC = "jira_epic"


class AssigneeType(StrEnum):
    UNASSIGNED = "unassigned"
    AI = "ai"
    HUMAN = "human"


VALID_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.BACKLOG: frozenset({
        TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.QUEUED: frozenset({
        TaskStatus.SPEC_CREATION, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.SPEC_CREATION: frozenset({
        TaskStatus.PLANNING, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.PLANNING: frozenset({
        TaskStatus.CODING, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.CODING: frozenset({
        TaskStatus.QA_REVIEW, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.QA_REVIEW: frozenset({
        TaskStatus.QA_FIXING,
        TaskStatus.CODE_REVIEW,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }),
    TaskStatus.QA_FIXING: frozenset({
        TaskStatus.QA_REVIEW, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.CODE_REVIEW: frozenset({
        TaskStatus.AWAITING_REVIEW, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.AWAITING_REVIEW: frozenset({
        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED
    }),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


@dataclass
class ExecutionProgress:
    current_phase: str = ""
    total_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0
    current_subtask_id: str | None = None
    qa_cycle: int = 0
    steps_executed: int = 0

    @property
    def progress_pct(self) -> float:
        if self.total_subtasks == 0:
            return 0.0
        return self.completed_subtasks / self.total_subtasks


@dataclass
class Task:
    id: TaskId
    project_id: ProjectId
    title: str
    description: str
    status: TaskStatus = TaskStatus.BACKLOG
    complexity: ComplexityTier | None = None
    spec: Spec | None = None
    plan: ImplementationPlan | None = None
    qa_report: QAReport | None = None
    execution_progress: ExecutionProgress = field(default_factory=ExecutionProgress)
    story_id: StoryId | None = None
    assignee_type: AssigneeType = AssigneeType.UNASSIGNED
    source: TaskSource = TaskSource.MANUAL
    source_ref: str | None = None
    worktree_path: str | None = None
    branch_name: str | None = None
    pr_url: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def start_pipeline(self) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        events.extend(self.transition_to(TaskStatus.QUEUED))
        events.append(TaskStarted(task_id=str(self.id)))
        return events

    def transition_to(self, new_status: TaskStatus) -> list[DomainEvent]:
        allowed = VALID_TASK_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition: {self.status!r} -> {new_status!r}")
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now(UTC)
        return [
            TaskStatusChanged(
                task_id=str(self.id), old_status=old_status, new_status=new_status
            )
        ]

    def mark_failed(self, error: str) -> list[DomainEvent]:
        self.error_message = error
        events = self.transition_to(TaskStatus.FAILED)
        events.append(TaskFailed(task_id=str(self.id), error=error))
        return events

    def mark_completed(self) -> list[DomainEvent]:
        events = self.transition_to(TaskStatus.COMPLETED)
        events.append(TaskCompleted(task_id=str(self.id)))
        return events

    def mark_cancelled(self) -> list[DomainEvent]:
        events = self.transition_to(TaskStatus.CANCELLED)
        events.append(TaskCancelled(task_id=str(self.id)))
        return events

    def start_code_review(self) -> list[DomainEvent]:
        events = self.transition_to(TaskStatus.CODE_REVIEW)
        events.append(TaskCodeReviewStarted(task_id=str(self.id)))
        return events

    def await_human_review(self) -> list[DomainEvent]:
        events = self.transition_to(TaskStatus.AWAITING_REVIEW)
        events.append(TaskAwaitingHumanReview(task_id=str(self.id)))
        return events

    def approve(self, reviewer: str = "") -> list[DomainEvent]:
        events = self.transition_to(TaskStatus.COMPLETED)
        events.append(TaskApproved(task_id=str(self.id), reviewer=reviewer))
        return events

    def assign_to(self, assignee_type: AssigneeType) -> None:
        self.assignee_type = assignee_type
        self.updated_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        project_id: ProjectId,
        title: str,
        description: str,
        story_id: StoryId | None = None,
        source: TaskSource = TaskSource.MANUAL,
        source_ref: str | None = None,
    ) -> tuple[Task, list[DomainEvent]]:
        task_id = TaskId.generate()
        task = cls(
            id=task_id,
            project_id=project_id,
            title=title,
            description=description,
            story_id=story_id,
            source=source,
            source_ref=source_ref,
        )
        events: list[DomainEvent] = [
            TaskCreated(
                task_id=str(task_id), project_id=str(project_id), title=title
            )
        ]
        return task, events
