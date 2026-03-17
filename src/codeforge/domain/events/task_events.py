from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class TaskCreated(DomainEvent):
    task_id: str = ""
    project_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class TaskStarted(DomainEvent):
    task_id: str = ""


@dataclass(frozen=True)
class TaskCompleted(DomainEvent):
    task_id: str = ""


@dataclass(frozen=True)
class TaskFailed(DomainEvent):
    task_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class TaskCancelled(DomainEvent):
    task_id: str = ""


@dataclass(frozen=True)
class TaskStatusChanged(DomainEvent):
    task_id: str = ""
    old_status: str = ""
    new_status: str = ""


@dataclass(frozen=True)
class TaskCodeReviewStarted(DomainEvent):
    task_id: str = ""


@dataclass(frozen=True)
class TaskAwaitingHumanReview(DomainEvent):
    task_id: str = ""


@dataclass(frozen=True)
class TaskApproved(DomainEvent):
    task_id: str = ""
    reviewer: str = ""
