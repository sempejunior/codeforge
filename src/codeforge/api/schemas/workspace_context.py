from __future__ import annotations

from pydantic import BaseModel


class WorkspaceContextResponseSchema(BaseModel):
    team_id: str
    consolidated_markdown: str
    documents_used: list[str]
    projects_with_context: int
    projects_without_context: int
