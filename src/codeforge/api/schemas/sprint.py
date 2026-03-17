from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class SprintCreateSchema(BaseModel):
    name: str
    start_date: date
    end_date: date
    story_ids: list[str] = Field(default_factory=list)


class SprintMetricsSchema(BaseModel):
    tasks_done: int
    tasks_total: int
    stories_done: int
    stories_total: int
    completion_pct: float


class SprintResponseSchema(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date
    story_ids: list[str]
    status: str
    metrics: SprintMetricsSchema
    created_at: datetime
    updated_at: datetime
