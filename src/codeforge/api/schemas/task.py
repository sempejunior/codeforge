from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TaskCreateSchema(BaseModel):
    project_id: str
    title: str
    description: str
    story_id: str | None = None
    source: str = "manual"
    source_ref: str | None = None


class TaskAssignSchema(BaseModel):
    assignee_type: str


class TaskTransitionSchema(BaseModel):
    status: str


class ExecutionProgressSchema(BaseModel):
    current_phase: str
    total_subtasks: int
    completed_subtasks: int
    failed_subtasks: int
    current_subtask_id: str | None
    qa_cycle: int
    steps_executed: int
    progress_pct: float


class TaskResponseSchema(BaseModel):
    id: str
    project_id: str
    story_id: str | None
    title: str
    description: str
    status: str
    complexity: str | None
    assignee_type: str
    source: str
    source_ref: str | None
    worktree_path: str | None
    branch_name: str | None
    pr_url: str | None
    error_message: str | None
    execution_progress: ExecutionProgressSchema
    created_at: datetime
    updated_at: datetime


class TaskPushResponseSchema(BaseModel):
    pr_url: str
