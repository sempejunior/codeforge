from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.project import Project
from ..value_objects.project_id import ProjectId
from ..value_objects.team_id import TeamId


class ProjectRepositoryPort(ABC):
    @abstractmethod
    async def save(self, project: Project) -> None: ...

    @abstractmethod
    async def get_by_id(self, project_id: ProjectId) -> Project | None: ...

    @abstractmethod
    async def list_all(self) -> list[Project]: ...

    @abstractmethod
    async def list_by_team(self, team_id: TeamId) -> list[Project]: ...

    @abstractmethod
    async def delete(self, project_id: ProjectId) -> None: ...
