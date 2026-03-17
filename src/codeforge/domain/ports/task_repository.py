from __future__ import annotations

from abc import ABC, abstractmethod

from ..entities.task import Task, TaskStatus
from ..value_objects.project_id import ProjectId
from ..value_objects.task_id import TaskId


class TaskRepositoryPort(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None: ...

    @abstractmethod
    async def get_by_id(self, task_id: TaskId) -> Task | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: ProjectId, status: TaskStatus | None = None
    ) -> list[Task]: ...

    @abstractmethod
    async def delete(self, task_id: TaskId) -> None: ...
