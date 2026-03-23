from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.team import Team
from ..value_objects.team_id import TeamId


class TeamRepositoryPort(ABC):
    @abstractmethod
    async def save(self, team: Team) -> None: ...

    @abstractmethod
    async def get_by_id(self, team_id: TeamId) -> Team | None: ...

    @abstractmethod
    async def list_all(self) -> list[Team]: ...

    @abstractmethod
    async def delete(self, team_id: TeamId) -> None: ...
