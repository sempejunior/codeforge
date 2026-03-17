from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.story import Story, StoryStatus
from ..value_objects.demand_id import DemandId
from ..value_objects.sprint_id import SprintId
from ..value_objects.story_id import StoryId


class StoryRepositoryPort(ABC):
    @abstractmethod
    async def save(self, story: Story) -> None: ...

    @abstractmethod
    async def get_by_id(self, story_id: StoryId) -> Story | None: ...

    @abstractmethod
    async def list_by_demand(
        self, demand_id: DemandId, status: StoryStatus | None = None
    ) -> list[Story]: ...

    @abstractmethod
    async def list_by_sprint(self, sprint_id: SprintId) -> list[Story]: ...

    @abstractmethod
    async def delete(self, story_id: StoryId) -> None: ...
