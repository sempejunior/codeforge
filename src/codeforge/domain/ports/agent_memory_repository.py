from __future__ import annotations

from abc import ABC, abstractmethod

from codeforge.domain.entities.agent_memory import AgentMemory
from codeforge.domain.value_objects.project_id import ProjectId


class AgentMemoryRepositoryPort(ABC):
    @abstractmethod
    async def save(self, memory: AgentMemory) -> None: ...

    @abstractmethod
    async def get(self, project_id: ProjectId, key: str) -> AgentMemory | None: ...

    @abstractmethod
    async def list_for_project(self, project_id: ProjectId) -> list[AgentMemory]: ...

    @abstractmethod
    async def delete(self, memory_id: str) -> None: ...
