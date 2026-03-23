from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TeamDocumentCreateSchema(BaseModel):
    team_id: str
    title: str
    kind: str
    parent_id: str | None = None
    content: str = ""
    linked_project_id: str | None = None
    linked_repository_id: str | None = None
    source: str = "manual"


class TeamDocumentUpdateSchema(BaseModel):
    title: str | None = None
    content: str | None = None
    parent_id: str | None = None


class TeamDocumentResponseSchema(BaseModel):
    id: str
    team_id: str
    title: str
    kind: str
    parent_id: str | None
    content: str
    linked_project_id: str | None
    linked_repository_id: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class TeamWorkspaceResponseSchema(BaseModel):
    team_id: str
    documents: list[TeamDocumentResponseSchema] = Field(default_factory=list)
