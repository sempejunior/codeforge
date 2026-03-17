from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from codeforge.api.dependencies import RepositoryContainer
from codeforge.api.routers import agents, demands, projects, sprints, stories, tasks
from codeforge.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    init_database,
)
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyAgentSessionRepository,
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
    )

    app.include_router(projects.router)
    app.include_router(demands.router)
    app.include_router(stories.router)
    app.include_router(sprints.router)
    app.include_router(tasks.router)
    app.include_router(agents.router)

    return app


app = create_app()
