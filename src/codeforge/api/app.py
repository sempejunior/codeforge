from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from codeforge.api.dependencies import RepositoryContainer
from codeforge.api.routers import (
    agents,
    ai,
    demands,
    intelligence,
    projects,
    repositories,
    settings,
    skills,
    sprints,
    stories,
    tasks,
    team_documents,
    teams,
)
from codeforge.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    init_database,
)
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


def _load_env_file() -> None:
    env_file = Path(__file__).parents[3] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in os.environ:
            os.environ[key] = value.strip()


def create_app(database_url: str | None = None) -> FastAPI:
    _load_env_file()
    resolved_database_url = database_url or os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/kodejutso",
    )
    engine = create_engine(resolved_database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await init_database(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="CodeForge API", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.analysis_jobs = {}
    app.state.generation_jobs = {}
    app.state.repositories = RepositoryContainer(
        team_document_repository=SqlAlchemyTeamDocumentRepository(session_factory),
        team_repository=SqlAlchemyTeamRepository(session_factory),
        task_repository=SqlAlchemyTaskRepository(session_factory),
        project_repository=SqlAlchemyProjectRepository(session_factory),
        repository_store=SqlAlchemyRepositoryStore(session_factory),
        demand_repository=SqlAlchemyDemandRepository(session_factory),
        story_repository=SqlAlchemyStoryRepository(session_factory),
        sprint_repository=SqlAlchemySprintRepository(session_factory),
        agent_session_repository=SqlAlchemyAgentSessionRepository(session_factory),
        agent_skill_repository=SqlAlchemyAgentSkillRepository(session_factory),
        agent_memory_repository=SqlAlchemyAgentMemoryRepository(session_factory),
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        msg = str(exc.orig) if exc.orig else str(exc)
        return JSONResponse(status_code=409, content={"detail": f"Conflict: {msg}"})

    app.include_router(projects.router)
    app.include_router(repositories.router)
    app.include_router(ai.router)
    app.include_router(teams.router)
    app.include_router(team_documents.router)
    app.include_router(demands.router)
    app.include_router(stories.router)
    app.include_router(sprints.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)
    app.include_router(intelligence.router)
    app.include_router(settings.router)
    app.include_router(skills.router)

    return app


app = create_app()
