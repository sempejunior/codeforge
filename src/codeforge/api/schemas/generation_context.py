from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationContextItemSchema(BaseModel):
    id: str
    kind: str
    title: str
    preview: str
    selected: bool
    source: str


class GenerationContextResponseSchema(BaseModel):
    team_id: str
    demand_id: str
    selected_project_ids: list[str] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    projects_with_context: int
    projects_without_context: int
    items: list[GenerationContextItemSchema] = Field(default_factory=list)
