from __future__ import annotations

from pathlib import Path

import pytest

from codeforge.domain.entities.agent import AgentType
from codeforge.infrastructure.tools.base import ToolContext, truncate_output
from codeforge.infrastructure.tools.edit_tool import EditTool
from codeforge.infrastructure.tools.glob_tool import GlobTool
from codeforge.infrastructure.tools.read_tool import ReadTool
from codeforge.infrastructure.tools.registry import build_default_registry
from codeforge.infrastructure.tools.write_tool import WriteTool


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def ctx(project_dir: Path) -> ToolContext:
    return ToolContext(cwd=project_dir, project_dir=project_dir)


def test_truncate_output_short_string():
    s = "hello world"
    assert truncate_output(s) == s


def test_truncate_output_long_string():
    s = "x" * 200_000
    result = truncate_output(s)
    assert len(result.encode()) <= 110_000
    assert "truncated" in result


@pytest.mark.asyncio
async def test_read_existing_file(ctx, project_dir):
    f = project_dir / "test.py"
    f.write_text("line1\nline2\nline3\n")
    tool = ReadTool()
    result = await tool.execute(tool.input_schema(file_path="test.py"), ctx)
    assert not result.is_error
    assert "line1" in result.content
    assert "line2" in result.content


@pytest.mark.asyncio
async def test_read_missing_file(ctx):
    tool = ReadTool()
    result = await tool.execute(tool.input_schema(file_path="missing.py"), ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_read_path_traversal_blocked(ctx):
    tool = ReadTool()
    result = await tool.execute(tool.input_schema(file_path="../../etc/passwd"), ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_read_with_offset(ctx, project_dir):
    f = project_dir / "multi.txt"
    f.write_text("\n".join(f"line{i}" for i in range(1, 11)))
    tool = ReadTool()
    result = await tool.execute(tool.input_schema(file_path="multi.txt", offset=5, limit=3), ctx)
    assert not result.is_error
    assert "line5" in result.content
    assert "line6" in result.content


@pytest.mark.asyncio
async def test_write_creates_file(ctx, project_dir):
    tool = WriteTool()
    result = await tool.execute(
        tool.input_schema(file_path="newfile.txt", content="hello\nworld\n"), ctx
    )
    assert not result.is_error
    assert (project_dir / "newfile.txt").read_text() == "hello\nworld\n"


@pytest.mark.asyncio
async def test_write_creates_parent_dirs(ctx, project_dir):
    tool = WriteTool()
    result = await tool.execute(
        tool.input_schema(file_path="nested/deep/file.txt", content="content"), ctx
    )
    assert not result.is_error
    assert (project_dir / "nested" / "deep" / "file.txt").exists()


@pytest.mark.asyncio
async def test_write_path_traversal_blocked(ctx):
    tool = WriteTool()
    result = await tool.execute(
        tool.input_schema(file_path="../../outside.txt", content="bad"), ctx
    )
    assert result.is_error


@pytest.mark.asyncio
async def test_edit_replaces_string(ctx, project_dir):
    f = project_dir / "code.py"
    f.write_text("def foo(): pass\n")
    tool = EditTool()
    result = await tool.execute(
        tool.input_schema(file_path="code.py", old_string="foo", new_string="bar"), ctx
    )
    assert not result.is_error
    assert f.read_text() == "def bar(): pass\n"


@pytest.mark.asyncio
async def test_edit_not_found_errors(ctx, project_dir):
    f = project_dir / "code.py"
    f.write_text("def foo(): pass\n")
    tool = EditTool()
    result = await tool.execute(
        tool.input_schema(file_path="code.py", old_string="nonexistent", new_string="bar"), ctx
    )
    assert result.is_error


@pytest.mark.asyncio
async def test_edit_duplicate_without_replace_all_errors(ctx, project_dir):
    f = project_dir / "code.py"
    f.write_text("foo foo\n")
    tool = EditTool()
    result = await tool.execute(
        tool.input_schema(file_path="code.py", old_string="foo", new_string="bar"), ctx
    )
    assert result.is_error
    assert "2" in result.content


@pytest.mark.asyncio
async def test_edit_replace_all(ctx, project_dir):
    f = project_dir / "code.py"
    f.write_text("foo foo foo\n")
    tool = EditTool()
    result = await tool.execute(
        tool.input_schema(
            file_path="code.py", old_string="foo", new_string="bar", replace_all=True
        ),
        ctx,
    )
    assert not result.is_error
    assert f.read_text() == "bar bar bar\n"


@pytest.mark.asyncio
async def test_edit_identical_strings_errors(ctx, project_dir):
    f = project_dir / "code.py"
    f.write_text("hello\n")
    tool = EditTool()
    result = await tool.execute(
        tool.input_schema(file_path="code.py", old_string="hello", new_string="hello"), ctx
    )
    assert result.is_error


@pytest.mark.asyncio
async def test_glob_finds_files(ctx, project_dir):
    (project_dir / "a.py").touch()
    (project_dir / "b.py").touch()
    (project_dir / "c.txt").touch()
    tool = GlobTool()
    result = await tool.execute(tool.input_schema(pattern="*.py"), ctx)
    assert not result.is_error
    assert "a.py" in result.content
    assert "b.py" in result.content
    assert "c.txt" not in result.content


@pytest.mark.asyncio
async def test_glob_no_matches(ctx):
    tool = GlobTool()
    result = await tool.execute(tool.input_schema(pattern="*.xyz"), ctx)
    assert "No files found" in result.content


@pytest.mark.asyncio
async def test_glob_excludes_git_dir(ctx, project_dir):
    git_dir = project_dir / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    tool = GlobTool()
    result = await tool.execute(tool.input_schema(pattern="**/*"), ctx)
    assert ".git" not in result.content


def test_registry_registers_all_builtins():
    registry = build_default_registry()
    names = registry.registered_names()
    assert "Read" in names
    assert "Write" in names
    assert "Edit" in names
    assert "Bash" in names
    assert "Glob" in names
    assert "Grep" in names


def test_registry_tools_for_complexity_assessor(project_dir):
    registry = build_default_registry()
    ctx = ToolContext(cwd=project_dir, project_dir=project_dir)
    tools = registry.get_tools_for_agent(AgentType.COMPLEXITY_ASSESSOR, ctx)
    assert set(tools.keys()) == {"Read", "Glob", "Grep"}


def test_registry_tools_for_coder_has_all(project_dir):
    registry = build_default_registry()
    ctx = ToolContext(cwd=project_dir, project_dir=project_dir)
    tools = registry.get_tools_for_agent(AgentType.CODER, ctx)
    assert "Read" in tools
    assert "Write" in tools
    assert "Bash" in tools
    assert "Edit" in tools


def test_registry_qa_reviewer_no_web_tools(project_dir):
    registry = build_default_registry()
    ctx = ToolContext(cwd=project_dir, project_dir=project_dir)
    tools = registry.get_tools_for_agent(AgentType.QA_REVIEWER, ctx)
    assert "WebFetch" not in tools
    assert "WebSearch" not in tools
    assert "Bash" in tools


def test_bound_tool_name(project_dir):
    registry = build_default_registry()
    ctx = ToolContext(cwd=project_dir, project_dir=project_dir)
    bound = registry.get("Read").bind(ctx)
    assert bound.name == "Read"
