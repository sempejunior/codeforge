from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TeamCreateSchema(BaseModel):
    name: str
    description: str | None = None


class TeamResponseSchema(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
