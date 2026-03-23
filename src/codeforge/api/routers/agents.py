from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status

from codeforge.api.dependencies import RepositoryContainer, get_repositories
from codeforge.api.schemas.agent import (
    AgentSessionCreateSchema,
    AgentSessionResponseSchema,
    TokenUsageSchema,
)
from codeforge.domain.entities.agent import AgentSession, AgentType
from codeforge.domain.value_objects.model_id import ModelId
from codeforge.domain.value_objects.task_id import TaskId

router = APIRouter(tags=["agents"])


@router.post(
    "/api/agents",
    response_model=AgentSessionResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent_session(
    payload: AgentSessionCreateSchema,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> AgentSessionResponseSchema:
    agent_session = AgentSession(
        id=payload.id or str(uuid.uuid4()),
        task_id=payload.task_id,
        agent_type=AgentType(payload.agent_type),
        model=ModelId(payload.model),
    )
    await repositories.agent_session_repository.save(agent_session)
    return _to_response(agent_session)


@router.get("/api/agents/{session_id}", response_model=AgentSessionResponseSchema)
async def get_agent_session(
    session_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> AgentSessionResponseSchema:
    agent_session = await repositories.agent_session_repository.get_by_id(session_id)
    if agent_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return _to_response(agent_session)


@router.get("/api/agents", response_model=list[AgentSessionResponseSchema])
async def list_agent_sessions(
    task_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    repositories: RepositoryContainer = Depends(get_repositories),
) -> list[AgentSessionResponseSchema]:
    if task_id is not None:
        sessions = await repositories.agent_session_repository.list_by_task_id(TaskId(task_id))
    else:
        sessions = await repositories.agent_session_repository.list_all(limit=limit)
    return [_to_response(session) for session in sessions]


@router.websocket("/ws/agents/{session_id}/logs")
async def agent_logs_websocket(
    websocket: WebSocket,
    session_id: str,
    repositories: RepositoryContainer = Depends(get_repositories),
) -> None:
    await websocket.accept()
    session = await repositories.agent_session_repository.get_by_id(session_id)
    if session is None:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close(code=1008)
        return
    await websocket.send_json(_to_response(session).model_dump(mode="json"))
    await websocket.close()


def _to_response(agent_session: AgentSession) -> AgentSessionResponseSchema:
    return AgentSessionResponseSchema(
        id=agent_session.id,
        task_id=agent_session.task_id,
        agent_type=agent_session.agent_type.value,
        model=str(agent_session.model),
        outcome=agent_session.outcome.value if agent_session.outcome else None,
        steps_executed=agent_session.steps_executed,
        tool_call_count=agent_session.tool_call_count,
        usage=TokenUsageSchema(
            input_tokens=agent_session.usage.input_tokens,
            output_tokens=agent_session.usage.output_tokens,
            cache_read_tokens=agent_session.usage.cache_read_tokens,
            cache_write_tokens=agent_session.usage.cache_write_tokens,
            total=agent_session.usage.total,
        ),
        error=agent_session.error,
        started_at=agent_session.started_at,
        ended_at=agent_session.ended_at,
    )
