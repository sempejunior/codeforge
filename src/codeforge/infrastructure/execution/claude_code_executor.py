from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from codeforge.infrastructure.tools.base import ToolContext
from codeforge.infrastructure.tools.glob_tool import GlobTool
from codeforge.infrastructure.tools.read_tool import ReadTool


@dataclass
class ExecutionConfig:
    executor: str
    task_prompt: str
    worktree_path: str
    timeout_seconds: int = 600


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int
    output: str
    changed_files: list[str]
    diff: str


class ClaudeCodeExecutor:
    async def execute(self, config: ExecutionConfig) -> ExecutionResult:
        command = _build_command(config)
        output_parts: list[str] = []

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=config.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _consume_stream(stream: asyncio.StreamReader | None) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                output_parts.append(line.decode("utf-8", errors="replace"))

        try:
            await asyncio.wait_for(
                asyncio.gather(_consume_stream(process.stdout), _consume_stream(process.stderr)),
                timeout=config.timeout_seconds,
            )
            await asyncio.wait_for(process.wait(), timeout=config.timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            output_parts.append("\n[Execution timed out]\n")

        exit_code = int(process.returncode if process.returncode is not None else 1)
        changed_files, diff = await _collect_git_changes(Path(config.worktree_path))
        return ExecutionResult(
            success=exit_code == 0,
            exit_code=exit_code,
            output="".join(output_parts),
            changed_files=changed_files,
            diff=diff,
        )


async def build_task_prompt(
    task_title: str,
    task_description: str,
    acceptance_criteria: list[str],
    worktree_path: str,
) -> str:
    project_dir = Path(worktree_path).resolve()
    context = ToolContext(cwd=project_dir, project_dir=project_dir)
    glob_tool = GlobTool()
    read_tool = ReadTool()

    listed = await glob_tool.execute(
        glob_tool.input_schema(pattern="**/*.py", path="src"),
        context,
    )
    files = [line.strip() for line in listed.content.splitlines() if line.strip() and "/" in line]
    files = files[:6]

    snippets: list[str] = []
    for file_path in files:
        file_read = await read_tool.execute(
            read_tool.input_schema(file_path=file_path, limit=60),
            context,
        )
        if not file_read.is_error:
            snippets.append(file_read.content)

    criteria_block = (
        "\n".join(f"- {item}" for item in acceptance_criteria) or "- Keep scope minimal"
    )
    context_block = "\n\n".join(snippets) if snippets else "No repository snippets collected."

    return (
        f"# Task\n\n"
        f"Title: {task_title}\n\n"
        f"Description:\n{task_description}\n\n"
        f"Acceptance Criteria:\n{criteria_block}\n\n"
        f"Repository Context:\n{context_block}\n\n"
        "Instructions:\n"
        "1. Implement only what is required by this task.\n"
        "2. Run relevant tests.\n"
        "3. Commit all changes with a clear message before finishing.\n"
    )


def _build_command(config: ExecutionConfig) -> list[str]:
    if config.executor == "claude":
        return ["claude", "-p", "--dangerously-skip-permissions", config.task_prompt]
    if config.executor == "opencode":
        return ["opencode", "run", config.task_prompt]
    if config.executor == "aider":
        return ["aider", "--message", config.task_prompt]
    raise ValueError(f"Unsupported executor: {config.executor}")


async def _collect_git_changes(worktree_path: Path) -> tuple[list[str], str]:
    status = await _run_git(worktree_path, "status", "--porcelain")
    tracked_changes = [ln for ln in status.splitlines() if ln and not ln.startswith("??")]
    if tracked_changes:
        changed = await _run_git(worktree_path, "diff", "--name-only")
        staged = await _run_git(worktree_path, "diff", "--cached", "--name-only")
        combined = sorted({*changed.splitlines(), *staged.splitlines()} - {""})
        diff = (await _run_git(worktree_path, "diff")) + (
            await _run_git(worktree_path, "diff", "--cached")
        )
        return combined, diff

    previous_exists = await _run_git_allow_error(worktree_path, "rev-parse", "--verify", "HEAD~1")
    if previous_exists[0] != 0:
        return [], ""

    changed = await _run_git(worktree_path, "diff", "--name-only", "HEAD~1..HEAD")
    diff = await _run_git(worktree_path, "diff", "HEAD~1..HEAD")
    return [line for line in changed.splitlines() if line.strip()], diff


async def _run_git(worktree_path: Path, *args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(worktree_path),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(error)
    return stdout.decode("utf-8", errors="replace")


async def _run_git_allow_error(worktree_path: Path, *args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(worktree_path),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return (
        int(process.returncode if process.returncode is not None else 1),
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )
