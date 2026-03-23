from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.task import (
    ExecutionProgressSchema,
    TaskAssignSchema,
    TaskCreateSchema,
    TaskPushResponseSchema,
    TaskResponseSchema,
    TaskTransitionSchema,
)
from codeforge.application.use_cases.push_task_to_github import push_task_to_github
from codeforge.domain.entities.task import AssigneeType, Task, TaskSource, TaskStatus
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.story_id import StoryId
from codeforge.domain.value_objects.task_id import TaskId
from codeforge.domain.value_objects.team_id import TeamId
from codeforge.infrastructure.git.git_service import GitService
from codeforge.infrastructure.integrations.github_gateway import GitHubGateway

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
    return task_to_response(task)


@router.get("/api/tasks", response_model=list[TaskResponseSchema])
async def list_tasks(
    project_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[TaskResponseSchema]:
    try:
        status_value = TaskStatus(status_filter) if status_filter else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid status: {status_filter}",
        ) from None

    if project_id is None and team_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either project_id or team_id is required",
        )

    tasks = []
    if project_id is not None:
        tasks = await repositories.task_repository.list_by_project(
            project_id=ProjectId(project_id),
            status=status_value,
        )
    else:
        assert team_id is not None
        typed_team_id = TeamId(team_id)
        projects = await repositories.project_repository.list_by_team(typed_team_id)
        for project in projects:
            tasks.extend(
                await repositories.task_repository.list_by_project(project.id, status=status_value)
            )
        tasks.sort(key=lambda task: task.created_at, reverse=True)
    return [task_to_response(task) for task in tasks]


@router.get("/api/tasks/{task_id}", response_model=TaskResponseSchema)
async def get_task(
    task_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task_to_response(task)


@router.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    await repositories.task_repository.delete(task.id)


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
    return task_to_response(task)


@router.post("/api/tasks/{task_id}/transition", response_model=TaskResponseSchema)
async def transition_task(
    task_id: str,
    payload: TaskTransitionSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        task.transition_to(TaskStatus(payload.status))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    await repositories.task_repository.save(task)
    return task_to_response(task)


@router.post("/api/tasks/{task_id}/push", response_model=TaskPushResponseSchema)
async def push_task(
    task_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> TaskPushResponseSchema:
    task = await repositories.task_repository.get_by_id(TaskId(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    project = await repositories.project_repository.get_by_id(task.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    result = await push_task_to_github(
        task=task,
        project=project,
        task_repo=repositories.task_repository,
        github_gateway=GitHubGateway(),
        git_service=GitService(),
        acceptance_criteria=_extract_acceptance_criteria(task.description),
    )
    return TaskPushResponseSchema(pr_url=result.pr_url)


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
    await websocket.send_json(task_to_response(task).model_dump(mode="json"))
    await websocket.close()


def task_to_response(task: Task) -> TaskResponseSchema:
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
        pr_url=task.pr_url,
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


def _extract_acceptance_criteria(description: str) -> list[str]:
    criteria = [
        line.strip("- ").strip()
        for line in description.splitlines()
        if line.strip().startswith("-")
    ]
    if not criteria:
        return ["Implement task exactly as requested", "Run relevant tests"]
    return criteria
