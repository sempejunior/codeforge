from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AgentSkillCreate(BaseModel):
    name: str
    content: str
    always_active: bool = True
    agent_type: str | None = None


class AgentSkillUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    always_active: bool | None = None


class AgentSkillResponse(BaseModel):
    id: str
    name: str
    content: str
    always_active: bool
    project_id: str | None
    agent_type: str | None
    created_at: datetime
    updated_at: datetime


class AgentMemoryUpsert(BaseModel):
    key: str
    content: str


class AgentMemoryResponse(BaseModel):
    id: str
    project_id: str
    key: str
    content: str
    updated_at: datetime
