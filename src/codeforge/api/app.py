from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from codeforge.api.dependencies import RepositoryContainer
from codeforge.api.routers import agents, demands, intelligence, projects, sprints, stories, tasks
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
    SqlAlchemySprintRepository,
    SqlAlchemyStoryRepository,
    SqlAlchemyTaskRepository,
)


def create_app(database_url: str = "sqlite+aiosqlite:///./codeforge.db") -> FastAPI:
    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await init_database(engine)
        yield
        await engine.dispose()

    app = FastAPI(title="CodeForge API", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.repositories = RepositoryContainer(
        task_repository=SqlAlchemyTaskRepository(session_factory),
        project_repository=SqlAlchemyProjectRepository(session_factory),
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
    app.include_router(demands.router)
    app.include_router(stories.router)
    app.include_router(sprints.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)
    app.include_router(intelligence.router)

    return app


app = create_app()
