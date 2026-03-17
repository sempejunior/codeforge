from __future__ import annotations

from dataclasses import dataclass, field

from codeforge.domain.entities.agent import TokenUsage
from codeforge.domain.entities.plan import ImplementationPlan
from codeforge.domain.entities.qa_report import QAReport
from codeforge.domain.entities.spec import Spec


@dataclass
class SpecPipelineResult:
    success: bool
    spec: Spec | None = None
    error: str | None = None
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    phases_completed: int = 0


@dataclass
class QALoopResult:
    success: bool
    qa_report: QAReport | None = None
    error: str | None = None
    cycles: int = 0
    total_usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class SubtaskExecutionResult:
    completed_count: int = 0
    stuck_count: int = 0
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class BuildPipelineResult:
    success: bool
    plan: ImplementationPlan | None = None
    qa_report: QAReport | None = None
    error: str | None = None
    total_usage: TokenUsage = field(default_factory=TokenUsage)
