from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LinkedProjectSchema(BaseModel):
    project_id: str
    base_branch: str = "main"


class DemandCreateSchema(BaseModel):
    title: str
    business_objective: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    linked_projects: list[LinkedProjectSchema] = Field(default_factory=list)


class DemandResponseSchema(BaseModel):
    id: str
    title: str
    business_objective: str
    acceptance_criteria: list[str]
    linked_projects: list[LinkedProjectSchema]
    status: str
    created_at: datetime
    updated_at: datetime


class DemandBreakdownCompleteSchema(BaseModel):
    total_tasks: int
