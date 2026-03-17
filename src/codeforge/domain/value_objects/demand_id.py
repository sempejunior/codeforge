from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class DemandId:
    value: str

    def __post_init__(self) -> None:
        uuid.UUID(self.value)

    @classmethod
    def generate(cls) -> DemandId:
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
