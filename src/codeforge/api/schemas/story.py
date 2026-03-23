from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StoryCreateSchema(BaseModel):
    demand_id: str
    project_id: str | None = None
    repository_ids: list[str] = Field(default_factory=list)
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    technical_references: list[str] = Field(default_factory=list)
    linked_projects: list[str] = Field(default_factory=list)


class StoryAddToSprintSchema(BaseModel):
    sprint_id: str


class StoryBreakdownRunSchema(BaseModel):
    repo_path: str | None = None
    project_id: str
    repository_id: str | None = None


class StoryUpdateSchema(BaseModel):
    project_id: str | None = None
    repository_ids: list[str] | None = None
    title: str | None = None
    description: str | None = None
    acceptance_criteria: list[str] | None = None
    technical_references: list[str] | None = None
    linked_projects: list[str] | None = None
    status: str | None = None


class StoryResponseSchema(BaseModel):
    id: str
    demand_id: str
    project_id: str | None
    repository_ids: list[str]
    title: str
    description: str
    acceptance_criteria: list[str]
    technical_references: list[str]
    linked_projects: list[str]
    sprint_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
