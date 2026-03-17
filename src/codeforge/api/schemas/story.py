from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StoryCreateSchema(BaseModel):
    demand_id: str
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class StoryAddToSprintSchema(BaseModel):
    sprint_id: str


class StoryResponseSchema(BaseModel):
    id: str
    demand_id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    sprint_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
