from __future__ import annotations

from pydantic import BaseModel


class InlineAssistRequestSchema(BaseModel):
    action: str
    text: str
    team_id: str | None = None
    demand_id: str | None = None
    project_id: str | None = None


class InlineAssistResponseSchema(BaseModel):
    result: str
