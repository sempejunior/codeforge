from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codeforge.infrastructure.persistence.database import get_session
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyAgentMemoryRepository,
    SqlAlchemyAgentSessionRepository,
    SqlAlchemyAgentSkillRepository,
    SqlAlchemyDemandRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemyRepositoryStore,
    SqlAlchemySprintRepository,
    SqlAlchemyStoryRepository,
    SqlAlchemyTaskRepository,
    SqlAlchemyTeamDocumentRepository,
    SqlAlchemyTeamRepository,
)


@dataclass(frozen=True)
class RepositoryContainer:
    team_document_repository: SqlAlchemyTeamDocumentRepository
    team_repository: SqlAlchemyTeamRepository
    task_repository: SqlAlchemyTaskRepository
    project_repository: SqlAlchemyProjectRepository
    repository_store: SqlAlchemyRepositoryStore
    demand_repository: SqlAlchemyDemandRepository
    story_repository: SqlAlchemyStoryRepository
    sprint_repository: SqlAlchemySprintRepository
    agent_session_repository: SqlAlchemyAgentSessionRepository
    agent_skill_repository: SqlAlchemyAgentSkillRepository
    agent_memory_repository: SqlAlchemyAgentMemoryRepository


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
