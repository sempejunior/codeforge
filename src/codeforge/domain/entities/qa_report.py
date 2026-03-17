from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class QAVerdict(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class QAIssue:
    title: str
    severity: IssueSeverity
    description: str
    file_path: str | None = None
    suggested_fix: str | None = None


@dataclass
class QAReport:
    verdict: QAVerdict
    issues: list[QAIssue] = field(default_factory=list)
    iteration: int = 1
    tests_passed: bool = False
    build_passed: bool = False
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def critical_issues(self) -> list[QAIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]

    def has_recurring_issues(self, history: list[QAReport], threshold: int = 3) -> bool:
        all_reports = [*history, self]
        title_counts: dict[str, int] = {}
        for report in all_reports:
            for issue in report.issues:
                title_counts[issue.title] = title_counts.get(issue.title, 0) + 1
        return any(count >= threshold for count in title_counts.values())
