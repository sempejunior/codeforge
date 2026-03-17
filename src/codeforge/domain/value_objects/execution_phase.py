from __future__ import annotations

from enum import StrEnum


class ExecutionPhase(StrEnum):
    IDLE = "idle"
    SPEC_CREATION = "spec_creation"
    PLANNING = "planning"
    CODING = "coding"
    QA_REVIEW = "qa_review"
    QA_FIXING = "qa_fixing"
    COMPLETE = "complete"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"


VALID_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]] = {
    ExecutionPhase.IDLE: frozenset({ExecutionPhase.SPEC_CREATION}),
    ExecutionPhase.SPEC_CREATION: frozenset({ExecutionPhase.PLANNING, ExecutionPhase.FAILED}),
    ExecutionPhase.PLANNING: frozenset({ExecutionPhase.CODING, ExecutionPhase.FAILED}),
    ExecutionPhase.CODING: frozenset({
        ExecutionPhase.QA_REVIEW,
        ExecutionPhase.RATE_LIMITED,
        ExecutionPhase.AUTH_FAILURE,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.QA_REVIEW: frozenset({
        ExecutionPhase.QA_FIXING,
        ExecutionPhase.COMPLETE,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.QA_FIXING: frozenset({
        ExecutionPhase.QA_REVIEW,
        ExecutionPhase.COMPLETE,
        ExecutionPhase.FAILED,
    }),
    ExecutionPhase.RATE_LIMITED: frozenset({ExecutionPhase.CODING, ExecutionPhase.FAILED}),
    ExecutionPhase.AUTH_FAILURE: frozenset({ExecutionPhase.CODING, ExecutionPhase.FAILED}),
    ExecutionPhase.COMPLETE: frozenset(),
    ExecutionPhase.FAILED: frozenset(),
}


def is_valid_transition(from_phase: ExecutionPhase, to_phase: ExecutionPhase) -> bool:
    return to_phase in VALID_TRANSITIONS.get(from_phase, frozenset())


def is_terminal(phase: ExecutionPhase) -> bool:
    return phase in (ExecutionPhase.COMPLETE, ExecutionPhase.FAILED)
