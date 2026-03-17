from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.task import (
    ExecutionProgressSchema,
    TaskAssignSchema,
    TaskCreateSchema,
    TaskResponseSchema,
    TaskTransitionSchema,
)
from codeforge.domain.entities.task import AssigneeType, Task, TaskSource, TaskStatus
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId

router = APIRouter(tags=["tasks"])


@router.post("/api/tasks", response_model=TaskResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task, _ = Task.create(
        project_id=ProjectId(payload.project_id),
        title=payload.title,
        description=payload.description,
        story_id=StoryId(payload.story_id) if payload.story_id else None,
        source=TaskSource(payload.source),
        source_ref=payload.source_ref,
    )
    await repositories.task_repository.save(task)
    return _to_response(task)


@router.get("/api/tasks", response_model=list[TaskResponseSchema])
async def list_tasks(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[TaskResponseSchema]:
    status_value = TaskStatus(status_filter) if status_filter else None
    tasks = await repositories.task_repository.list_by_project(
        project_id=ProjectId(project_id),
        status=status_value,
    )
    return [_to_response(task) for task in tasks]


@router.get("/api/tasks/{task_id}", response_model=TaskResponseSchema)
async def get_task(
    task_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_response(task)


@router.post("/api/tasks/{task_id}/assign", response_model=TaskResponseSchema)
async def assign_task(
    task_id: str,
    payload: TaskAssignSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.assign_to(AssigneeType(payload.assignee_type))
    await repositories.task_repository.save(task)
    return _to_response(task)


@router.post("/api/tasks/{task_id}/transition", response_model=TaskResponseSchema)
async def transition_task(
    task_id: str,
    payload: TaskTransitionSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.transition_to(TaskStatus(payload.status))
    await repositories.task_repository.save(task)
    return _to_response(task)


@router.websocket("/ws/tasks/{task_id}/progress")
async def task_progress_websocket(
    websocket: WebSocket,
    task_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    await websocket.accept()
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        await websocket.send_json({"error": "Task not found"})
        await websocket.close(code=1008)
        return
    await websocket.send_json(_to_response(task).model_dump(mode="json"))
    await websocket.close()


def _to_response(task: Task) -> TaskResponseSchema:
    return TaskResponseSchema(
        id=str(task.id),
        project_id=str(task.project_id),
        story_id=str(task.story_id) if task.story_id else None,
        title=task.title,
        description=task.description,
        status=task.status.value,
        complexity=task.complexity.value if task.complexity else None,
        assignee_type=task.assignee_type.value,
        source=task.source.value,
        source_ref=task.source_ref,
        worktree_path=task.worktree_path,
        branch_name=task.branch_name,
        error_message=task.error_message,
        execution_progress=ExecutionProgressSchema(
            current_phase=task.execution_progress.current_phase,
            total_subtasks=task.execution_progress.total_subtasks,
            completed_subtasks=task.execution_progress.completed_subtasks,
            failed_subtasks=task.execution_progress.failed_subtasks,
            current_subtask_id=task.execution_progress.current_subtask_id,
            qa_cycle=task.execution_progress.qa_cycle,
            steps_executed=task.execution_progress.steps_executed,
            progress_pct=task.execution_progress.progress_pct,
        ),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
