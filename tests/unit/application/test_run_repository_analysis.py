from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeforge.application.use_cases.run_repository_analysis import (
    AnalysisInput,
    run_repository_analysis,
)
from codeforge.domain.entities.repository import AnalysisStatus, Repository
from codeforge.domain.entities.team_document import TeamDocument, TeamDocumentKind
from codeforge.domain.value_objects.project_id import ProjectId
from codeforge.domain.value_objects.repository_id import RepositoryId


def _make_repository(tmp_path: Path) -> Repository:
    repo_dir = tmp_path / "test-repo"
    repo_dir.mkdir(exist_ok=True)
    (repo_dir / ".git").mkdir(exist_ok=True)
    return Repository.create(
        project_id=ProjectId.generate(),
        name="TestRepo",
        slug="acme/test-repo",
        repo_url="https://github.com/acme/test-repo",
        path=str(repo_dir),
    )


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    skill = tmp_path / "analyze-with-test"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: analyze-with-test\n"
        "description: Test analyzer\n"
        "category: analyze-codebase\n"
        "requires:\n"
        '  bins: ["python3"]\n'
        'command: ["echo", "{prompt}"]\n'
        "---\n"
        "\n# Analyze\n\n## Prompt\n\nAnalyze this codebase.\n\n## Notes\n\nDone.\n"
    )
    return tmp_path


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    return _make_repository(tmp_path)


@pytest.fixture
def store(repository: Repository) -> AsyncMock:
    mock = AsyncMock()
    mock.get_by_id.return_value = repository
    return mock


def _make_process(stdout: bytes = b"output", stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = AsyncMock()
    proc.wait = AsyncMock()
    return proc


async def test_success(store: AsyncMock, repository: Repository, skills_dir: Path) -> None:
    saved_statuses: list[str] = []

    async def capture_save(r: Repository) -> None:
        saved_statuses.append(r.analysis_status.value)

    store.save.side_effect = capture_save

    proc = _make_process(stdout=b"# Context: TestRepo\n\n## Stack\nPython")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await run_repository_analysis(
            AnalysisInput(repository_id=repository.id),
            store,
            skills_dir,
        )

    assert result.success is True
    assert "Context: TestRepo" in result.context_doc
    assert result.executor_used == "analyze-with-test"
    assert result.error is None

    assert len(saved_statuses) == 2
    assert saved_statuses[0] == "analyzing"
    assert saved_statuses[1] == "done"
    assert repository.context_doc == "# Context: TestRepo\n\n## Stack\nPython"


async def test_analyzing_status_saved_before_subprocess(
    store: AsyncMock, repository: Repository, skills_dir: Path
) -> None:
    saved_statuses: list[str] = []

    async def capture_save(r: Repository) -> None:
        saved_statuses.append(r.analysis_status.value)

    store.save.side_effect = capture_save

    proc = _make_process(stdout=b"output")
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        await run_repository_analysis(
            AnalysisInput(repository_id=repository.id),
            store,
            skills_dir,
        )

    assert saved_statuses[0] == "analyzing"


async def test_failure_exit_code(store: AsyncMock, repository: Repository, skills_dir: Path) -> None:
    repository.context_doc = "previous doc"
    proc = _make_process(stderr=b"some error", returncode=1)
    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await run_repository_analysis(
            AnalysisInput(repository_id=repository.id),
            store,
            skills_dir,
        )

    assert result.success is False
    assert "exited with code 1" in (result.error or "")

    final_save = store.save.call_args_list[-1][0][0]
    assert final_save.analysis_status == AnalysisStatus.ERROR
    assert final_save.context_doc == "previous doc"


async def test_timeout(store: AsyncMock, repository: Repository, skills_dir: Path) -> None:
    proc = AsyncMock()
    proc.communicate = AsyncMock(side_effect=TimeoutError)
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    proc.returncode = -9

    with patch("asyncio.create_subprocess_exec", return_value=proc):
        result = await run_repository_analysis(
            AnalysisInput(repository_id=repository.id, timeout_seconds=1),
            store,
            skills_dir,
        )

    assert result.success is False
    assert "timed out" in (result.error or "")
    proc.kill.assert_called_once()

    final_save = store.save.call_args_list[-1][0][0]
    assert final_save.analysis_status == AnalysisStatus.ERROR


async def test_no_executor_available(repository: Repository, tmp_path: Path) -> None:
    store = AsyncMock()
    store.get_by_id.return_value = repository

    empty_skills = tmp_path / "empty_skills"
    empty_skills.mkdir()

    result = await run_repository_analysis(
        AnalysisInput(repository_id=repository.id),
        store,
        empty_skills,
    )

    assert result.success is False
    assert "No analysis executor available" in (result.error or "")
    store.save.assert_not_called()


async def test_repository_not_found() -> None:
    store = AsyncMock()
    store.get_by_id.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await run_repository_analysis(
            AnalysisInput(repository_id=RepositoryId.generate()),
            store,
            Path("/tmp"),
        )


async def test_analysis_uses_remote_github_archive_when_repo_url_exists(
    store: AsyncMock,
    skills_dir: Path,
) -> None:
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        extracted_repo = temp_dir / "repo"
        extracted_repo.mkdir()
        remote_repository = Repository.create(
            project_id=ProjectId.generate(),
            name="RemoteRepo",
            slug="acme/remote-project",
            repo_url="https://github.com/acme/remote-project",
        )
        store.get_by_id.return_value = remote_repository
        github_gateway = AsyncMock()
        github_gateway.download_repository_archive.return_value = extracted_repo

        proc = _make_process(stdout=b"# Context: RemoteRepo")
        with patch("asyncio.create_subprocess_exec", return_value=proc):
            result = await run_repository_analysis(
                AnalysisInput(repository_id=remote_repository.id),
                store,
                skills_dir,
                github_gateway=github_gateway,
            )

    assert result.success is True
    assert github_gateway.download_repository_archive.await_count == 1
    kwargs = github_gateway.download_repository_archive.await_args.kwargs
    assert kwargs["repo"] == "acme/remote-project"
    assert kwargs["ref"] == "main"
    assert isinstance(kwargs["destination_dir"], Path)
