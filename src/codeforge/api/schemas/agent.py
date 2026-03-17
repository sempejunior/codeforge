from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentSessionCreateSchema(BaseModel):
    id: str
    task_id: str
    agent_type: str
    model: str


class TokenUsageSchema(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total: int


class AgentSessionResponseSchema(BaseModel):
    id: str
    task_id: str
    agent_type: str
    model: str
    outcome: str | None
    steps_executed: int
    tool_call_count: int
    usage: TokenUsageSchema
    error: str | None
    started_at: datetime
    ended_at: datetime | None
