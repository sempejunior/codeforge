from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..value_objects.project_id import ProjectId
from ..value_objects.team_id import TeamId


class CodeReviewMode(StrEnum):
    AI_ONLY = "ai_only"
    HUMAN_REQUIRED = "human_required"
    HUMAN_OPTIONAL = "human_optional"


@dataclass
class ProjectConfig:
    max_parallel_subtasks: int = 3
    max_qa_cycles: int = 3
    max_subtask_retries: int = 3
    auto_continue_delay_seconds: int = 3
    default_model: str = "anthropic:claude-sonnet-4-20250514"
    code_review_mode: CodeReviewMode = CodeReviewMode.AI_ONLY
    human_review_required: bool = False
    auto_start_tasks: bool = False
    breakdown_requires_approval: bool = True
    auto_merge: bool = False


@dataclass
class Project:
    id: ProjectId
    name: str
    team_id: TeamId | None = None
    config: ProjectConfig = field(default_factory=ProjectConfig)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        team_id: TeamId | None = None,
    ) -> Project:
        return cls(
            id=ProjectId.generate(),
            name=name,
            team_id=team_id,
        )
