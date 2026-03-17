from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class PhaseTransitioned(DomainEvent):
    task_id: str = ""
    from_phase: str = ""
    to_phase: str = ""


@dataclass(frozen=True)
class SubtaskStarted(DomainEvent):
    task_id: str = ""
    subtask_id: str = ""


@dataclass(frozen=True)
class SubtaskCompleted(DomainEvent):
    task_id: str = ""
    subtask_id: str = ""


@dataclass(frozen=True)
class SubtaskFailed(DomainEvent):
    task_id: str = ""
    subtask_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class QACycleCompleted(DomainEvent):
    task_id: str = ""
    iteration: int = 0
    verdict: str = ""
