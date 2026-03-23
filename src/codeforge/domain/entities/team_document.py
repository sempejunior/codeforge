from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..value_objects.project_id import ProjectId
from ..value_objects.repository_id import RepositoryId
from ..value_objects.team_document_id import TeamDocumentId
from ..value_objects.team_id import TeamId


class TeamDocumentKind(StrEnum):
    FOLDER = "folder"
    DOCUMENT = "document"


class TeamDocumentSource(StrEnum):
    MANUAL = "manual"
    GENERATED = "generated"
    SYSTEM = "system"


@dataclass
class TeamDocument:
    id: TeamDocumentId
    team_id: TeamId
    title: str
    kind: TeamDocumentKind
    parent_id: TeamDocumentId | None = None
    content: str = ""
    linked_project_id: ProjectId | None = None
    linked_repository_id: RepositoryId | None = None
    source: TeamDocumentSource = TeamDocumentSource.MANUAL
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create_folder(
        cls,
        team_id: TeamId,
        title: str,
        parent_id: TeamDocumentId | None = None,
        source: TeamDocumentSource = TeamDocumentSource.MANUAL,
        linked_project_id: ProjectId | None = None,
        linked_repository_id: RepositoryId | None = None,
    ) -> TeamDocument:
        return cls(
            id=TeamDocumentId.generate(),
            team_id=team_id,
            title=title,
            kind=TeamDocumentKind.FOLDER,
            parent_id=parent_id,
            source=source,
            linked_project_id=linked_project_id,
            linked_repository_id=linked_repository_id,
        )

    @classmethod
    def create_document(
        cls,
        team_id: TeamId,
        title: str,
        content: str = "",
        parent_id: TeamDocumentId | None = None,
        source: TeamDocumentSource = TeamDocumentSource.MANUAL,
        linked_project_id: ProjectId | None = None,
        linked_repository_id: RepositoryId | None = None,
    ) -> TeamDocument:
        return cls(
            id=TeamDocumentId.generate(),
            team_id=team_id,
            title=title,
            kind=TeamDocumentKind.DOCUMENT,
            parent_id=parent_id,
            content=content,
            source=source,
            linked_project_id=linked_project_id,
            linked_repository_id=linked_repository_id,
        )
