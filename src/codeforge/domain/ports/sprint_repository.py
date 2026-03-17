from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.sprint import Sprint, SprintStatus
from ..value_objects.sprint_id import SprintId


class SprintRepositoryPort(ABC):
    @abstractmethod
    async def save(self, sprint: Sprint) -> None: ...

    @abstractmethod
    async def get_by_id(self, sprint_id: SprintId) -> Sprint | None: ...

    @abstractmethod
    async def list_all(
        self, status: SprintStatus | None = None
    ) -> list[Sprint]: ...

    @abstractmethod
    async def get_active(self) -> Sprint | None: ...

    @abstractmethod
    async def delete(self, sprint_id: SprintId) -> None: ...
