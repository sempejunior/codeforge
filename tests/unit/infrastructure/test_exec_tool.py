from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.infrastructure.tools.base import ToolContext
from codeforge.infrastructure.tools.exec_tool import ExecInput, ExecTool


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def ctx(project_dir: Path) -> ToolContext:
    return ToolContext(cwd=project_dir, project_dir=project_dir)


@pytest.fixture
def tool() -> ExecTool:
    return ExecTool(timeout=10)


async def test_exec_echo(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="echo hello"), ctx)
    assert not result.is_error
    assert "hello" in result.content


async def test_exec_exit_code(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="exit 42"), ctx)
    assert result.is_error
    assert "Exit code: 42" in result.content


async def test_exec_stderr(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="echo err >&2"), ctx)
    assert "STDERR:" in result.content


async def test_exec_timeout(ctx: ToolContext) -> None:
    tool = ExecTool(timeout=1)
    result = await tool.execute(ExecInput(command="sleep 30"), ctx)
    assert result.is_error
    assert "Timeout" in result.content


async def test_deny_rm_rf(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="rm -rf /"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_deny_sudo(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="sudo apt install foo"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_deny_shutdown(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="shutdown -h now"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_deny_fork_bomb(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command=":(){ :|:& };:"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_allow_patterns(ctx: ToolContext) -> None:
    tool = ExecTool(allow_patterns=[r"^echo\b"])
    result = await tool.execute(ExecInput(command="echo allowed"), ctx)
    assert not result.is_error

    result = await tool.execute(ExecInput(command="ls /tmp"), ctx)
    assert result.is_error
    assert "allow list" in result.content


async def test_workspace_restriction_path_traversal(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="cat ../../../etc/passwd"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_workspace_restriction_absolute_path(
    tool: ExecTool, ctx: ToolContext
) -> None:
    result = await tool.execute(ExecInput(command="cat /etc/passwd"), ctx)
    assert result.is_error
    assert "Blocked" in result.content


async def test_working_dir_override(tool: ExecTool, ctx: ToolContext) -> None:
    sub = ctx.project_dir / "subdir"
    sub.mkdir()
    (sub / "hello.txt").write_text("hi")
    result = await tool.execute(ExecInput(command="cat hello.txt", working_dir=str(sub)), ctx)
    assert not result.is_error
    assert "hi" in result.content


async def test_working_dir_outside_project(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(ExecInput(command="ls", working_dir="/tmp"), ctx)
    assert result.is_error
    assert "outside" in result.content


async def test_custom_deny_patterns(ctx: ToolContext) -> None:
    tool = ExecTool(deny_patterns=[r"\bcurl\b"])
    result = await tool.execute(ExecInput(command="curl http://example.com"), ctx)
    assert result.is_error
    assert "Blocked" in result.content

    result = await tool.execute(ExecInput(command="echo safe"), ctx)
    assert not result.is_error


async def test_no_workspace_restriction(ctx: ToolContext) -> None:
    tool = ExecTool(restrict_to_workspace=False)
    result = await tool.execute(ExecInput(command="echo /etc/passwd"), ctx)
    assert not result.is_error


async def test_output_truncation(tool: ExecTool, ctx: ToolContext) -> None:
    result = await tool.execute(
        ExecInput(command="python3 -c \"print('x' * 50000)\""), ctx
    )
    assert "truncated" in result.content


async def test_properties(tool: ExecTool) -> None:
    assert tool.name == "Exec"
    assert tool.input_schema is ExecInput
    assert "shell command" in tool.description.lower()
