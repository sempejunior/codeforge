from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.infrastructure.execution.claude_code_executor import (
    ClaudeCodeExecutor,
    ExecutionConfig,
    build_task_prompt,
)


class _FakeStream:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeExecutorProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.stdout = _FakeStream(["ok\n"])
        self.stderr = _FakeStream([])

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        self.returncode = 1


class _FakeGitProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self._stdout = stdout.encode("utf-8")
        self._stderr = stderr.encode("utf-8")
        self.stdout = None
        self.stderr = None

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_execute_collects_output_and_diff(monkeypatch, tmp_path: Path) -> None:
    git_responses = [
        _FakeGitProcess(0, " M src/a.py\n"),
        _FakeGitProcess(0, "src/a.py\n"),
        _FakeGitProcess(0, ""),
        _FakeGitProcess(0, "diff-a"),
        _FakeGitProcess(0, ""),
    ]

    async def _fake_create_subprocess_exec(*command, **kwargs):
        del kwargs
        if command[0] == "git":
            return git_responses.pop(0)
        return _FakeExecutorProcess(returncode=0)

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_create_subprocess_exec)

    executor = ClaudeCodeExecutor()
    result = await executor.execute(
        ExecutionConfig(
            executor="claude",
            task_prompt="implement",
            worktree_path=str(tmp_path),
            timeout_seconds=30,
        )
    )

    assert result.success is True
    assert result.exit_code == 0
    assert "ok" in result.output
    assert result.changed_files == ["src/a.py"]
    assert "diff-a" in result.diff


@pytest.mark.asyncio
async def test_build_task_prompt_includes_context(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text("def run() -> None:\n    pass\n", encoding="utf-8")

    prompt = await build_task_prompt(
        task_title="Add feature",
        task_description="Implement module",
        acceptance_criteria=["must work"],
        worktree_path=str(tmp_path),
    )

    assert "Add feature" in prompt
    assert "Acceptance Criteria" in prompt
    assert "module.py" in prompt
