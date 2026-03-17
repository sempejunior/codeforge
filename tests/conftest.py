from __future__ import annotations

import pytest

from codeforge.domain.entities.plan import (
    ImplementationPlan,
    Phase,
    PhaseType,
    Subtask,
    WorkflowType,
)
from codeforge.domain.entities.task import Task
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.task_id import TaskId


@pytest.fixture
def project_id() -> ProjectId:
    return ProjectId.generate()


@pytest.fixture
def task_id() -> TaskId:
    return TaskId.generate()


@pytest.fixture
def sample_task(project_id: ProjectId) -> Task:
    task, _ = Task.create(
        project_id=project_id,
        title="Add JWT authentication",
        description="Implement JWT-based auth for all API endpoints",
    )
    return task


@pytest.fixture
def sample_plan() -> ImplementationPlan:
    return ImplementationPlan(
        feature="JWT authentication",
        workflow_type=WorkflowType.MODIFICATION,
        phases=[
            Phase(
                number=1,
                name="Setup",
                phase_type=PhaseType.SETUP,
                subtasks=[
                    Subtask(id="1.1", title="Install deps", description="Install jwt libraries"),
                    Subtask(
                        id="1.2",
                        title="Create config",
                        description="Create JWT config",
                        depends_on=["1.1"],
                    ),
                ],
            ),
            Phase(
                number=2,
                name="Implementation",
                phase_type=PhaseType.IMPLEMENTATION,
                depends_on=[1],
                subtasks=[
                    Subtask(
                        id="2.1", title="Auth middleware", description="Create JWT middleware"
                    ),
                    Subtask(
                        id="2.2",
                        title="Login endpoint",
                        description="Create /login endpoint",
                        depends_on=["2.1"],
                    ),
                ],
            ),
        ],
    )
