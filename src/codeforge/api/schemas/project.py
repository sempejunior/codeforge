from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectConfigSchema(BaseModel):
    max_parallel_subtasks: int
    max_qa_cycles: int
    max_subtask_retries: int
    auto_continue_delay_seconds: int
    default_model: str
    code_review_mode: str
    human_review_required: bool
    auto_start_tasks: bool
    breakdown_requires_approval: bool
    auto_merge: bool


class ProjectConfigUpdateSchema(BaseModel):
    max_parallel_subtasks: int | None = None
    max_qa_cycles: int | None = None
    max_subtask_retries: int | None = None
    auto_continue_delay_seconds: int | None = None
    default_model: str | None = None
    code_review_mode: str | None = None
    human_review_required: bool | None = None
    auto_start_tasks: bool | None = None
    breakdown_requires_approval: bool | None = None
    auto_merge: bool | None = None


class ProjectCreateSchema(BaseModel):
    name: str
    team_id: str | None = None


class ProjectUpdateSchema(BaseModel):
    name: str | None = None
    team_id: str | None = None
    config: ProjectConfigUpdateSchema | None = None


class ProjectResponseSchema(BaseModel):
    id: str
    name: str
    team_id: str | None
    config: ProjectConfigSchema
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
