from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.plan import ImplementationPlan


class PlanRepositoryPort(ABC):
    @abstractmethod
    async def save(self, plan: ImplementationPlan, task_id: str) -> None: ...

    @abstractmethod
    async def get_by_task_id(self, task_id: str) -> ImplementationPlan | None: ...

    @abstractmethod
    async def delete(self, task_id: str) -> None: ...
