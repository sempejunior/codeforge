from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.team_document import TeamDocument
from ..value_objects.project_id import ProjectId
from ..value_objects.repository_id import RepositoryId
from ..value_objects.team_document_id import TeamDocumentId
from ..value_objects.team_id import TeamId


class TeamDocumentRepositoryPort(ABC):
    @abstractmethod
    async def save(self, document: TeamDocument) -> None: ...

    @abstractmethod
    async def get_by_id(self, document_id: TeamDocumentId) -> TeamDocument | None: ...

    @abstractmethod
    async def list_by_team(self, team_id: TeamId) -> list[TeamDocument]: ...

    @abstractmethod
    async def list_by_project(self, project_id: ProjectId) -> list[TeamDocument]: ...

    @abstractmethod
    async def list_by_repository(self, repository_id: RepositoryId) -> list[TeamDocument]: ...

    @abstractmethod
    async def find_generated_context_document(
        self,
        team_id: TeamId,
        project_id: ProjectId,
    ) -> TeamDocument | None: ...

    @abstractmethod
    async def find_generated_repo_context_document(
        self,
        team_id: TeamId,
        repository_id: RepositoryId,
    ) -> TeamDocument | None: ...

    @abstractmethod
    async def find_folder_for_project(
        self,
        team_id: TeamId,
        project_id: ProjectId,
    ) -> TeamDocument | None: ...

    @abstractmethod
    async def find_folder_for_repository(
        self,
        team_id: TeamId,
        repository_id: RepositoryId,
    ) -> TeamDocument | None: ...

    @abstractmethod
    async def delete(self, document_id: TeamDocumentId) -> None: ...
