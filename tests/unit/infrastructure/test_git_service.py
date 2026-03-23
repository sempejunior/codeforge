from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.infrastructure.git.git_service import GitService


class _FakeProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self._stdout = stdout.encode("utf-8")
        self._stderr = stderr.encode("utf-8")

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_create_worktree_builds_expected_branch_and_path(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    async def _fake_create_subprocess_exec(*command, **kwargs):
        del kwargs
        calls.append(tuple(str(c) for c in command))
        return _FakeProcess(0, "", "")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    service = GitService()
    info = await service.create_worktree(str(tmp_path), "task-123")

    assert info.branch == "codeforge/task-task-123"
    assert info.path.endswith(".codeforge/worktrees/task-task-123")
    assert calls[0][-5:] == (
        "worktree",
        "add",
        "-B",
        "codeforge/task-task-123",
        str(tmp_path / ".codeforge" / "worktrees" / "task-task-123"),
    )


@pytest.mark.asyncio
async def test_commit_returns_head_hash(monkeypatch, tmp_path: Path) -> None:
    outputs = [
        _FakeProcess(0, "", ""),
        _FakeProcess(0, "", ""),
        _FakeProcess(0, "abc123\n", ""),
    ]

    async def _fake_create_subprocess_exec(*command, **kwargs):
        del command, kwargs
        return outputs.pop(0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    service = GitService()
    commit_hash = await service.commit(str(tmp_path), "feat: test")
    assert commit_hash == "abc123"


@pytest.mark.asyncio
async def test_get_changed_files_parses_output(monkeypatch, tmp_path: Path) -> None:
    async def _fake_create_subprocess_exec(*command, **kwargs):
        del command, kwargs
        return _FakeProcess(0, "src/a.py\nsrc/b.py\n", "")

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    service = GitService()
    files = await service.get_changed_files(str(tmp_path), "main")
    assert files == ["src/a.py", "src/b.py"]


@pytest.mark.asyncio
async def test_remove_worktree_removes_branch(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    responses = [
        _FakeProcess(0, "codeforge/task-1\n", ""),
        _FakeProcess(0, f"{tmp_path}/.git\n", ""),
        _FakeProcess(0, "", ""),
        _FakeProcess(0, "", ""),
        _FakeProcess(0, "", ""),
    ]

    async def _fake_create_subprocess_exec(*command, **kwargs):
        del kwargs
        calls.append(tuple(str(c) for c in command))
        return responses.pop(0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    service = GitService()
    await service.remove_worktree(str(tmp_path / "wt"))

    assert any("worktree" in call and "remove" in call for call in calls)
    assert any("branch" in call and "-D" in call for call in calls)
