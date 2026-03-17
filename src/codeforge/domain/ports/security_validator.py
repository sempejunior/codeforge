from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ValidationResult:
    allowed: bool
    reason: str | None = None


class SecurityValidatorPort(ABC):
    @abstractmethod
    def validate_command(self, command: str) -> ValidationResult: ...

    @abstractmethod
    def validate_path(self, path: str, project_root: str) -> ValidationResult: ...
