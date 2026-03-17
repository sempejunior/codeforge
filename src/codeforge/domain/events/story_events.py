from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class StoryCreated(DomainEvent):
    story_id: str = ""
    demand_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class StoryAddedToSprint(DomainEvent):
    story_id: str = ""
    sprint_id: str = ""


@dataclass(frozen=True)
class StoryStatusChanged(DomainEvent):
    story_id: str = ""
    old_status: str = ""
    new_status: str = ""
