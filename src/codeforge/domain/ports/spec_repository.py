from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.spec import Spec


class SpecRepositoryPort(ABC):
    @abstractmethod
    async def save(self, spec: Spec) -> None: ...

    @abstractmethod
    async def get_by_task_id(self, task_id: str) -> Spec | None: ...

    @abstractmethod
    async def delete(self, task_id: str) -> None: ...
