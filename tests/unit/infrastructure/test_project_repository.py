from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from codeforge.domain.entities.project import Project
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.infrastructure.persistence.models import Base
from codeforge.infrastructure.persistence.repositories import (
    SqlAlchemyProjectRepository,
    SqlAlchemyRepositoryStore,
)
from codeforge.domain.value_objects.project_id import ProjectId


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def project_repo(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyProjectRepository:
    return SqlAlchemyProjectRepository(session_factory)


@pytest.fixture
def repository_store(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyRepositoryStore:
    return SqlAlchemyRepositoryStore(session_factory)


def test_project_create_defaults() -> None:
    project = Project.create(name="Test")
    assert project.name == "Test"
    assert project.team_id is None


async def test_save_and_load_project(project_repo: SqlAlchemyProjectRepository) -> None:
    project = Project.create(name="Test")
    await project_repo.save(project)

    loaded = await project_repo.get_by_id(project.id)
    assert loaded is not None
    assert loaded.name == "Test"
    assert loaded.team_id is None


async def test_repository_save_and_load_context_doc(
    project_repo: SqlAlchemyProjectRepository,
    repository_store: SqlAlchemyRepositoryStore,
) -> None:
    project = Project.create(name="Test")
    await project_repo.save(project)

    repository = Repository.create(
        project_id=project.id,
        name="test-repo",
        slug="acme/test-repo",
        repo_url="https://github.com/acme/test-repo",
    )
    repository.context_doc = "# Context document"
    repository.analysis_status = AnalysisStatus.DONE
    await repository_store.save(repository)

    loaded = await repository_store.get_by_id(repository.id)
    assert loaded is not None
    assert loaded.context_doc == "# Context document"
    assert loaded.analysis_status == AnalysisStatus.DONE


async def test_repository_default_analysis_status(
    project_repo: SqlAlchemyProjectRepository,
    repository_store: SqlAlchemyRepositoryStore,
) -> None:
    project = Project.create(name="Test2")
    await project_repo.save(project)

    repository = Repository.create(
        project_id=project.id,
        name="test-repo-2",
        slug="acme/test-repo-2",
        repo_url="https://github.com/acme/test-repo-2",
    )
    await repository_store.save(repository)

    loaded = await repository_store.get_by_id(repository.id)
    assert loaded is not None
    assert loaded.analysis_status == AnalysisStatus.NONE
    assert loaded.context_doc is None


async def test_repository_update_analysis_status(
    project_repo: SqlAlchemyProjectRepository,
    repository_store: SqlAlchemyRepositoryStore,
) -> None:
    project = Project.create(name="Test3")
    await project_repo.save(project)

    repository = Repository.create(
        project_id=project.id,
        name="test-repo-3",
        slug="acme/test-repo-3",
        repo_url="https://github.com/acme/test-repo-3",
    )
    await repository_store.save(repository)

    repository.analysis_status = AnalysisStatus.ANALYZING
    await repository_store.save(repository)

    loaded = await repository_store.get_by_id(repository.id)
    assert loaded is not None
    assert loaded.analysis_status == AnalysisStatus.ANALYZING

    repository.analysis_status = AnalysisStatus.ERROR
    await repository_store.save(repository)

    loaded = await repository_store.get_by_id(repository.id)
    assert loaded is not None
    assert loaded.analysis_status == AnalysisStatus.ERROR
