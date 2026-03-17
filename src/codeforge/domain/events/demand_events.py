from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class DemandCreated(DomainEvent):
    demand_id: str = ""
    title: str = ""


@dataclass(frozen=True)
class DemandBreakdownRequested(DomainEvent):
    demand_id: str = ""


@dataclass(frozen=True)
class DemandBreakdownCompleted(DomainEvent):
    demand_id: str = ""
    total_tasks: int = 0


@dataclass(frozen=True)
class DemandStatusChanged(DomainEvent):
    demand_id: str = ""
    old_status: str = ""
    new_status: str = ""
