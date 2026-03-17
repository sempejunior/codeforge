from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeforge.infrastructure.persistence.database import get_session
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyAgentSessionRepository,
    SqlAlchemyDemandRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySprintRepository,
    SqlAlchemyStoryRepository,
    SqlAlchemyTaskRepository,
)


@dataclass(frozen=True)
class RepositoryContainer:
    task_repository: SqlAlchemyTaskRepository
    project_repository: SqlAlchemyProjectRepository
    demand_repository: SqlAlchemyDemandRepository
    story_repository: SqlAlchemyStoryRepository
    sprint_repository: SqlAlchemySprintRepository
    agent_session_repository: SqlAlchemyAgentSessionRepository


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> AsyncSession:
    async for session in get_session(session_factory):
        return session
    raise RuntimeError("Failed to create database session")


def get_repositories(request: Request) -> RepositoryContainer:
    return request.app.state.repositories
