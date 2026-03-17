from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class SubtaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    STUCK = "stuck"


class PhaseType(StrEnum):
    SETUP = "setup"
    IMPLEMENTATION = "implementation"
    INTEGRATION = "integration"
    CLEANUP = "cleanup"


class WorkflowType(StrEnum):
    GREENFIELD = "greenfield"
    MODIFICATION = "modification"
    REFACTOR = "refactor"
    BUGFIX = "bugfix"


@dataclass
class QASignoff:
    verdict: str
    issues_count: int
    iteration: int
    signed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Subtask:
    id: str
    title: str
    description: str
    files_to_modify: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: SubtaskStatus = SubtaskStatus.PENDING
    attempt_count: int = 0
    max_retries: int = 3

    def can_retry(self) -> bool:
        return self.attempt_count < self.max_retries

    def mark_in_progress(self) -> None:
        self.status = SubtaskStatus.IN_PROGRESS
        self.attempt_count += 1

    def mark_completed(self) -> None:
        self.status = SubtaskStatus.COMPLETED

    def mark_failed(self) -> None:
        self.status = SubtaskStatus.FAILED

    def mark_stuck(self) -> None:
        self.status = SubtaskStatus.STUCK


@dataclass
class Phase:
    number: int
    name: str
    phase_type: PhaseType
    subtasks: list[Subtask] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)

    def is_complete(self) -> bool:
        return all(
            s.status in (SubtaskStatus.COMPLETED, SubtaskStatus.STUCK)
            for s in self.subtasks
        )

    def get_subtask(self, subtask_id: str) -> Subtask | None:
        return next((s for s in self.subtasks if s.id == subtask_id), None)


@dataclass
class ImplementationPlan:
    feature: str
    workflow_type: WorkflowType
    phases: list[Phase] = field(default_factory=list)
    final_acceptance: list[str] = field(default_factory=list)
    qa_signoff: QASignoff | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_subtask(self, subtask_id: str) -> Subtask | None:
        for phase in self.phases:
            subtask = phase.get_subtask(subtask_id)
            if subtask is not None:
                return subtask
        return None

    def get_next_pending_subtask(self, stuck_ids: set[str]) -> Subtask | None:
        completed_ids = {
            s.id
            for phase in self.phases
            for s in phase.subtasks
            if s.status == SubtaskStatus.COMPLETED
        }
        completed_phases = {p.number for p in self.phases if p.is_complete()}

        for phase in self.phases:
            if not all(dep in completed_phases for dep in phase.depends_on):
                continue
            for subtask in phase.subtasks:
                if subtask.status != SubtaskStatus.PENDING:
                    continue
                if subtask.id in stuck_ids:
                    continue
                if all(dep in completed_ids for dep in subtask.depends_on):
                    return subtask
        return None

    def mark_subtask_completed(self, subtask_id: str) -> None:
        subtask = self.get_subtask(subtask_id)
        if subtask is not None:
            subtask.mark_completed()
        self.updated_at = datetime.now(UTC)

    def all_subtasks_done(self) -> bool:
        return all(
            s.status in (SubtaskStatus.COMPLETED, SubtaskStatus.STUCK)
            for phase in self.phases
            for s in phase.subtasks
        )

    def total_subtasks(self) -> int:
        return sum(len(p.subtasks) for p in self.phases)

    def completed_subtasks(self) -> int:
        return sum(
            1
            for phase in self.phases
            for s in phase.subtasks
            if s.status == SubtaskStatus.COMPLETED
        )
