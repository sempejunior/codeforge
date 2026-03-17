from __future__ import annotations

import pytest

from codeforge.domain.services.phase_state_machine import (
    InvalidPhaseTransitionError,
    PhaseStateMachine,
)
from codeforge.domain.value_objects.execution_phase import ExecutionPhase


def test_initial_state_is_idle():
    sm = PhaseStateMachine()
    assert sm.current == ExecutionPhase.IDLE


def test_valid_transition_idle_to_spec_creation():
    sm = PhaseStateMachine()
    sm.transition(ExecutionPhase.SPEC_CREATION)
    assert sm.current == ExecutionPhase.SPEC_CREATION


def test_valid_full_pipeline_transition():
    sm = PhaseStateMachine()
    for phase in [
        ExecutionPhase.SPEC_CREATION,
        ExecutionPhase.PLANNING,
        ExecutionPhase.CODING,
        ExecutionPhase.QA_REVIEW,
        ExecutionPhase.COMPLETE,
    ]:
        sm.transition(phase)
    assert sm.current == ExecutionPhase.COMPLETE


def test_valid_qa_loop_transition():
    sm = PhaseStateMachine(ExecutionPhase.QA_REVIEW)
    sm.transition(ExecutionPhase.QA_FIXING)
    sm.transition(ExecutionPhase.QA_REVIEW)
    sm.transition(ExecutionPhase.COMPLETE)
    assert sm.current == ExecutionPhase.COMPLETE


def test_rate_limited_then_resume():
    sm = PhaseStateMachine(ExecutionPhase.CODING)
    sm.transition(ExecutionPhase.RATE_LIMITED)
    sm.transition(ExecutionPhase.CODING)
    assert sm.current == ExecutionPhase.CODING


def test_invalid_transition_raises():
    sm = PhaseStateMachine()
    with pytest.raises(InvalidPhaseTransitionError):
        sm.transition(ExecutionPhase.CODING)


def test_terminal_complete_no_transition():
    sm = PhaseStateMachine(ExecutionPhase.COMPLETE)
    with pytest.raises(InvalidPhaseTransitionError):
        sm.transition(ExecutionPhase.CODING)


def test_terminal_failed_no_transition():
    sm = PhaseStateMachine(ExecutionPhase.FAILED)
    with pytest.raises(InvalidPhaseTransitionError):
        sm.transition(ExecutionPhase.IDLE)


def test_is_terminal_complete():
    sm = PhaseStateMachine(ExecutionPhase.COMPLETE)
    assert sm.is_terminal() is True


def test_is_terminal_failed():
    sm = PhaseStateMachine(ExecutionPhase.FAILED)
    assert sm.is_terminal() is True


def test_is_not_terminal_coding():
    sm = PhaseStateMachine(ExecutionPhase.CODING)
    assert sm.is_terminal() is False


def test_can_transition_false_for_invalid():
    sm = PhaseStateMachine(ExecutionPhase.IDLE)
    assert sm.can_transition(ExecutionPhase.COMPLETE) is False


def test_can_transition_true_for_valid():
    sm = PhaseStateMachine(ExecutionPhase.IDLE)
    assert sm.can_transition(ExecutionPhase.SPEC_CREATION) is True


def test_any_active_phase_can_fail():
    for phase in [
        ExecutionPhase.SPEC_CREATION,
        ExecutionPhase.PLANNING,
        ExecutionPhase.CODING,
        ExecutionPhase.QA_REVIEW,
        ExecutionPhase.QA_FIXING,
    ]:
        sm = PhaseStateMachine(phase)
        assert sm.can_transition(ExecutionPhase.FAILED), f"{phase} should allow -> FAILED"
