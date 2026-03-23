from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..value_objects.team_id import TeamId


@dataclass
class Team:
    id: TeamId
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(cls, name: str, description: str | None = None) -> Team:
        return cls(
            id=TeamId.generate(),
            name=name,
            description=description,
        )
