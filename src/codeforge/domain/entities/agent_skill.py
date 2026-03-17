from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from codeforge.domain.entities.agent import AgentType
from codeforge.domain.value_objects.project_id import ProjectId


@dataclass
class AgentSkill:
    id: str
    name: str
    content: str
    always_active: bool
    project_id: ProjectId | None
    agent_type: AgentType | None
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def create(
        id: str,
        name: str,
        content: str,
        always_active: bool = True,
        project_id: ProjectId | None = None,
        agent_type: AgentType | None = None,
    ) -> AgentSkill:
        now = datetime.now(UTC)
        return AgentSkill(
            id=id,
            name=name,
            content=content,
            always_active=always_active,
            project_id=project_id,
            agent_type=agent_type,
            created_at=now,
            updated_at=now,
        )

    def update_content(self, content: str) -> None:
        self.content = content
        self.updated_at = datetime.now(UTC)

    def update(
        self,
        name: str | None = None,
        content: str | None = None,
        always_active: bool | None = None,
    ) -> None:
        if name is not None:
            self.name = name
        if content is not None:
            self.content = content
        if always_active is not None:
            self.always_active = always_active
        self.updated_at = datetime.now(UTC)
