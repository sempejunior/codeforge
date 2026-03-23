from __future__ import annotations

from pydantic import BaseModel


class TeamContextRepositorySchema(BaseModel):
    repository_id: str
    project_id: str
    project_name: str
    name: str
    path: str | None
    repo_url: str | None
    source_label: str
    analysis_status: str
    analysis_executor: str | None
    has_context: bool
    is_selected: bool
    local_path_status: str


class TeamContextResponseSchema(BaseModel):
    team_id: str
    selected_project_ids: list[str]
    ready_repositories: int
    total_repositories: int
    missing_context_repositories: int
    consolidated_context: str
    repositories: list[TeamContextRepositorySchema]
