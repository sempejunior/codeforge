from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ..value_objects.model_id import ModelId
from ..value_objects.thinking_level import ThinkingLevel


class AgentType(StrEnum):
    COMPLEXITY_ASSESSOR = "complexity_assessor"
    SPEC_WRITER = "spec_writer"
    SPEC_CRITIC = "spec_critic"
    PLANNER = "planner"
    CODER = "coder"
    QA_REVIEWER = "qa_reviewer"
    QA_FIXER = "qa_fixer"


class SessionOutcome(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"
    ERROR = "error"
    MAX_STEPS = "max_steps"
    CONTEXT_WINDOW = "context_window"


@dataclass(frozen=True)
class AgentConfig:
    tools: frozenset[str]
    thinking_level: ThinkingLevel
    max_steps: int
    context_window_warning_pct: float = 0.85
    context_window_abort_pct: float = 0.90
    convergence_nudge_pct: float | None = None


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AgentSession:
    id: str
    task_id: str
    agent_type: AgentType
    model: ModelId
    outcome: SessionOutcome | None = None
    steps_executed: int = 0
    tool_call_count: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None

    def finish(self, outcome: SessionOutcome, error: str | None = None) -> None:
        self.outcome = outcome
        self.error = error
        self.ended_at = datetime.now(UTC)
