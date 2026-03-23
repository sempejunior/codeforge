from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.repository import Repository
from ..value_objects.project_id import ProjectId
from ..value_objects.repository_id import RepositoryId


class RepositoryStorePort(ABC):
    @abstractmethod
    async def save(self, repository: Repository) -> None: ...

    @abstractmethod
    async def get_by_id(self, repository_id: RepositoryId) -> Repository | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: ProjectId) -> list[Repository]: ...

    @abstractmethod
    async def list_all(self) -> list[Repository]: ...

    @abstractmethod
    async def get_by_repo_url(self, repo_url: str) -> Repository | None: ...

    @abstractmethod
    async def delete(self, repository_id: RepositoryId) -> None: ...
