from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class SprintCreated(DomainEvent):
    sprint_id: str = ""
    name: str = ""


@dataclass(frozen=True)
class SprintStarted(DomainEvent):
    sprint_id: str = ""


@dataclass(frozen=True)
class SprintCompleted(DomainEvent):
    sprint_id: str = ""
    stories_done: int = 0
    stories_total: int = 0


@dataclass(frozen=True)
class SprintStatusChanged(DomainEvent):
    sprint_id: str = ""
    old_status: str = ""
    new_status: str = ""
