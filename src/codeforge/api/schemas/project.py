from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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


class ProjectCreateSchema(BaseModel):
    name: str
    path: str
    repo_url: str | None = None
    default_branch: str = "main"


class ProjectResponseSchema(BaseModel):
    id: str
    name: str
    path: str
    repo_url: str | None
    default_branch: str
    config: ProjectConfigSchema
    created_at: datetime
    updated_at: datetime
