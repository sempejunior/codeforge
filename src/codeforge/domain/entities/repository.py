from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..value_objects.project_id import ProjectId
from ..value_objects.repository_id import RepositoryId


class RepositoryStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AnalysisStatus(StrEnum):
    NONE = "none"
    ANALYZING = "analyzing"
    DONE = "done"
    ERROR = "error"


@dataclass
class Repository:
    id: RepositoryId
    project_id: ProjectId
    name: str
    slug: str
    repo_url: str
    default_branch: str = "main"
    path: str | None = None
    status: RepositoryStatus = RepositoryStatus.ACTIVE
    context_doc: str | None = None
    analysis_status: AnalysisStatus = AnalysisStatus.NONE
    analysis_executor: str | None = None
    analysis_error: str | None = None
    local_path_hint: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        project_id: ProjectId,
        name: str,
        slug: str,
        repo_url: str,
        default_branch: str = "main",
        path: str | None = None,
    ) -> Repository:
        return cls(
            id=RepositoryId.generate(),
            project_id=project_id,
            name=name,
            slug=slug,
            repo_url=repo_url,
            default_branch=default_branch,
            path=path,
        )

    def archive(self) -> None:
        self.status = RepositoryStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)
