from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RepositoryCreateSchema(BaseModel):
    name: str
    slug: str
    repo_url: str
    default_branch: str = "main"


class RepositoryResponseSchema(BaseModel):
    id: str
    project_id: str
    name: str
    slug: str
    repo_url: str
    default_branch: str
    path: str | None
    status: str
    context_doc: str | None
    analysis_status: str
    analysis_executor: str | None
    analysis_error: str | None = None
    local_path_hint: str | None
    local_path_status: str
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
