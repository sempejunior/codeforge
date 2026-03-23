from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LinkedProjectSchema(BaseModel):
    project_id: str
    base_branch: str = "main"


class DemandCreateSchema(BaseModel):
    title: str
    business_objective: str
    team_id: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    linked_projects: list[LinkedProjectSchema] = Field(default_factory=list)


class DemandResponseSchema(BaseModel):
    id: str
    title: str
    business_objective: str
    team_id: str | None = None
    acceptance_criteria: list[str]
    linked_projects: list[LinkedProjectSchema]
    status: str
    generation_status: str = "none"
    generation_error: str | None = None
    created_at: datetime
    updated_at: datetime


class DemandUpdateSchema(BaseModel):
    title: str | None = None
    business_objective: str | None = None
    team_id: str | None = None
    acceptance_criteria: list[str] | None = None
    linked_projects: list[LinkedProjectSchema] | None = None


class DemandBreakdownCompleteSchema(BaseModel):
    total_tasks: int


class DemandAssistRequestSchema(BaseModel):
    description: str
    project_id: str


class DemandAssistantStorySchema(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str]


class DemandAssistResponseSchema(BaseModel):
    demand: DemandResponseSchema
    stories: list[DemandAssistantStorySchema]
    success: bool


class DemandGenerateStoriesSchema(BaseModel):
    selected_project_ids: list[str] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
