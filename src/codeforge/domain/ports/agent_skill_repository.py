from __future__ import annotations

from abc import ABC, abstractmethod

from codeforge.domain.entities.agent import AgentType
from codeforge.domain.entities.agent_skill import AgentSkill
from codeforge.domain.value_objects.project_id import ProjectId


class AgentSkillRepositoryPort(ABC):
    @abstractmethod
    async def save(self, skill: AgentSkill) -> None: ...

    @abstractmethod
    async def get(self, skill_id: str) -> AgentSkill | None: ...

    @abstractmethod
    async def list_for_agent(
        self,
        project_id: ProjectId | None,
        agent_type: AgentType | None,
        only_active: bool = True,
    ) -> list[AgentSkill]:
        """Returns skills matching the agent context.

        Includes global skills (project_id=None) and project-specific skills.
        Includes skills for the given agent_type and generic skills (agent_type=None).
        If only_active=True, returns only skills with always_active=True.
        """

    @abstractmethod
    async def list_by_project(self, project_id: ProjectId) -> list[AgentSkill]: ...

    @abstractmethod
    async def delete(self, skill_id: str) -> None: ...
