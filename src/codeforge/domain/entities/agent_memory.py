from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from codeforge.domain.value_objects.project_id import ProjectId


@dataclass
class AgentMemory:
    id: str
    project_id: ProjectId
    key: str
    content: str
    updated_at: datetime

    @staticmethod
    def create(
        id: str,
        project_id: ProjectId,
        key: str,
        content: str,
    ) -> AgentMemory:
        return AgentMemory(
            id=id,
            project_id=project_id,
            key=key,
            content=content,
            updated_at=datetime.now(UTC),
        )

    def update(self, content: str) -> None:
        self.content = content
        self.updated_at = datetime.now(UTC)
