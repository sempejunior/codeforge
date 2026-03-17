from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.demand import Demand, DemandStatus
from ..value_objects.demand_id import DemandId


class DemandRepositoryPort(ABC):
    @abstractmethod
    async def save(self, demand: Demand) -> None: ...

    @abstractmethod
    async def get_by_id(self, demand_id: DemandId) -> Demand | None: ...

    @abstractmethod
    async def list_all(
        self, status: DemandStatus | None = None
    ) -> list[Demand]: ...

    @abstractmethod
    async def delete(self, demand_id: DemandId) -> None: ...
