from __future__ import annotations

from ..entities.plan import ImplementationPlan, Subtask, SubtaskStatus


class CyclicDependencyError(Exception):
    pass


def resolve_execution_order(plan: ImplementationPlan) -> list[list[str]]:
    """Returns batches of subtask IDs that can execute in parallel.

    Each batch contains subtasks with no interdependencies. Respects
    phase ordering and intra-phase deps. Raises CyclicDependencyError
    if a cycle is detected.
    """
    all_subtasks: dict[str, Subtask] = {
        s.id: s for phase in plan.phases for s in phase.subtasks
    }
    phase_subtask_ids: dict[int, list[str]] = {
        phase.number: [s.id for s in phase.subtasks] for phase in plan.phases
    }

    completed: set[str] = set()
    phases_completed: set[int] = set()
    result: list[list[str]] = []

    while True:
        batch: list[str] = []

        for phase in plan.phases:
            if phase.number in phases_completed:
                continue
            if not all(dep in phases_completed for dep in phase.depends_on):
                continue

            for subtask_id in phase_subtask_ids[phase.number]:
                subtask = all_subtasks[subtask_id]
                if subtask.status in (SubtaskStatus.COMPLETED, SubtaskStatus.STUCK):
                    completed.add(subtask_id)
                    continue
                if subtask_id in completed:
                    continue
                if all(dep in completed for dep in subtask.depends_on):
                    batch.append(subtask_id)

        if not batch:
            unfinished = [
                sid for sid, st in all_subtasks.items()
                if st.status not in (SubtaskStatus.COMPLETED, SubtaskStatus.STUCK)
                and sid not in completed
            ]
            if unfinished:
                raise CyclicDependencyError(
                    f"Cyclic or unresolvable dependencies detected: {unfinished}"
                )
            break

        result.append(batch)
        completed.update(batch)

        for phase in plan.phases:
            if phase.number in phases_completed:
                continue
            if all(
                all_subtasks[sid].status in (SubtaskStatus.COMPLETED, SubtaskStatus.STUCK)
                or sid in completed
                for sid in phase_subtask_ids[phase.number]
            ):
                phases_completed.add(phase.number)

    return result


def get_ready_subtasks(plan: ImplementationPlan, stuck_ids: set[str]) -> list[str]:
    """Returns IDs of subtasks ready to execute (dependencies met, not stuck/done)."""
    completed_ids = {
        s.id
        for phase in plan.phases
        for s in phase.subtasks
        if s.status == SubtaskStatus.COMPLETED
    }
    completed_phases = {p.number for p in plan.phases if p.is_complete()}
    ready: list[str] = []

    for phase in plan.phases:
        if not all(dep in completed_phases for dep in phase.depends_on):
            continue
        for subtask in phase.subtasks:
            if subtask.status != SubtaskStatus.PENDING:
                continue
            if subtask.id in stuck_ids:
                continue
            if all(dep in completed_ids for dep in subtask.depends_on):
                ready.append(subtask.id)

    return ready
