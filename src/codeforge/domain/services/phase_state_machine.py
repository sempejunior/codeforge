from __future__ import annotations

from ..value_objects.execution_phase import (
    VALID_TRANSITIONS,
    ExecutionPhase,
    is_terminal,
)


class InvalidPhaseTransitionError(Exception):
    pass


class PhaseStateMachine:
    """Validates and manages execution phase transitions."""

    def __init__(self, initial: ExecutionPhase = ExecutionPhase.IDLE) -> None:
        self._current = initial

    @property
    def current(self) -> ExecutionPhase:
        return self._current

    def can_transition(self, to: ExecutionPhase) -> bool:
        return to in VALID_TRANSITIONS.get(self._current, frozenset())

    def transition(self, to: ExecutionPhase) -> None:
        if not self.can_transition(to):
            raise InvalidPhaseTransitionError(
                f"Cannot transition from {self._current!r} to {to!r}"
            )
        self._current = to

    def is_terminal(self) -> bool:
        return is_terminal(self._current)

    def allowed_transitions(self) -> frozenset[ExecutionPhase]:
        return VALID_TRANSITIONS.get(self._current, frozenset())
