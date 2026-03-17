from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ..value_objects.complexity import ComplexityTier


class SpecPhase(StrEnum):
    DISCOVERY = "discovery"
    REQUIREMENTS = "requirements"
    RESEARCH = "research"
    CONTEXT = "context"
    WRITING = "writing"
    CRITIQUE = "critique"
    VALIDATION = "validation"


@dataclass
class Spec:
    task_id: str
    complexity: ComplexityTier
    content: str = ""
    requirements: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    phases_completed: list[SpecPhase] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_complete(self) -> bool:
        return bool(self.content.strip())

    def add_phase(self, phase: SpecPhase) -> None:
        if phase not in self.phases_completed:
            self.phases_completed.append(phase)
            self.updated_at = datetime.now(UTC)
