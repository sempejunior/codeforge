from __future__ import annotations

from dataclasses import dataclass

from .base import DomainEvent


@dataclass(frozen=True)
class AgentSessionStarted(DomainEvent):
    session_id: str = ""
    task_id: str = ""
    agent_type: str = ""


@dataclass(frozen=True)
class AgentStepCompleted(DomainEvent):
    session_id: str = ""
    step_number: int = 0
    tool_calls: int = 0


@dataclass(frozen=True)
class AgentToolCalled(DomainEvent):
    session_id: str = ""
    tool_name: str = ""
    step_number: int = 0


@dataclass(frozen=True)
class AgentSessionCompleted(DomainEvent):
    session_id: str = ""
    outcome: str = ""
    steps_executed: int = 0
