from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import Repository
from codeforge.infrastructure.persistence.models import Base
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyProjectRepository,
    SqlAlchemyRepositoryStore,
)


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_save_and_list_repositories(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project_repo = SqlAlchemyProjectRepository(session_factory)
    repository_store = SqlAlchemyRepositoryStore(session_factory)

    project = Project.create(name="Payments")
    await project_repo.save(project)

    repository = Repository.create(
        project_id=project.id,
        name="payments-api",
        slug="acme/payments-api",
        repo_url="https://github.com/acme/payments-api",
    )
    await repository_store.save(repository)

    loaded = await repository_store.list_by_project(project.id)

    assert len(loaded) == 1
    assert loaded[0].slug == "acme/payments-api"


async def test_get_by_repo_url(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project_repo = SqlAlchemyProjectRepository(session_factory)
    repository_store = SqlAlchemyRepositoryStore(session_factory)

    project = Project.create(name="Payments")
    await project_repo.save(project)

    repository = Repository.create(
        project_id=project.id,
        name="payments-api",
        slug="acme/payments-api",
        repo_url="https://github.com/acme/payments-api",
    )
    await repository_store.save(repository)

    found = await repository_store.get_by_repo_url("https://github.com/acme/payments-api")
    assert found is not None
    assert found.id == repository.id

    not_found = await repository_store.get_by_repo_url("https://github.com/acme/nonexistent")
    assert not_found is None


async def test_list_all_repositories(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project_repo = SqlAlchemyProjectRepository(session_factory)
    repository_store = SqlAlchemyRepositoryStore(session_factory)

    project = Project.create(name="Payments")
    await project_repo.save(project)

    repo1 = Repository.create(
        project_id=project.id,
        name="payments-api",
        slug="acme/payments-api",
        repo_url="https://github.com/acme/payments-api",
    )
    repo2 = Repository.create(
        project_id=project.id,
        name="payments-web",
        slug="acme/payments-web",
        repo_url="https://github.com/acme/payments-web",
    )
    await repository_store.save(repo1)
    await repository_store.save(repo2)

    all_repos = await repository_store.list_all()
    assert len(all_repos) == 2
