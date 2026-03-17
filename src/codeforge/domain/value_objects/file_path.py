from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SafeFilePath:
    """A file path validated to be within the project root."""

    value: str

    @classmethod
    def create(cls, path: str, project_root: Path) -> SafeFilePath:
        resolved = (project_root / path).resolve()
        if not str(resolved).startswith(str(project_root.resolve())):
            raise ValueError(f"Path escapes project root: {path!r}")
        return cls(str(resolved.relative_to(project_root.resolve())))

    def to_absolute(self, project_root: Path) -> Path:
        return (project_root / self.value).resolve()
