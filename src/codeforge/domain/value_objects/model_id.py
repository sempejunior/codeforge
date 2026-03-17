from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelId:
    value: str

    def __post_init__(self) -> None:
        if ":" not in self.value:
            raise ValueError(f"ModelId must be 'provider:model', got: {self.value!r}")

    @property
    def provider(self) -> str:
        return self.value.split(":", 1)[0]

    @property
    def model(self) -> str:
        return self.value.split(":", 1)[1]

    def __str__(self) -> str:
        return self.value
