from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from codeforge.infrastructure.tools.base import (
    DefinedTool,
    ToolContext,
    ToolPermission,
    ToolResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120
_MAX_OUTPUT_CHARS = 30_000

_DEFAULT_DENY_PATTERNS: list[str] = [
    r"\brm\s+-[rf]{1,2}\b",
    r"\bdel\s+/[fq]\b",
    r"\brmdir\s+/s\b",
    r"(?:^|[;&|]\s*)format\b",
    r"\b(mkfs|diskpart)\b",
    r"\bdd\s+if=",
    r">\s*/dev/sd",
    r"\b(shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{.*\};\s*:",
    r"\bsudo\b",
    r"\bchmod\s+[0-7]*[2367][0-7]*\b",
]


class ExecInput(BaseModel):
    command: str = Field(description="The shell command to execute")
    working_dir: str | None = Field(
        default=None,
        description="Optional working directory override (must be within project)",
    )


class ExecTool(DefinedTool):
    """Shell execution tool with configurable security guards.

    Adapted from nanobot/agent/tools/shell.py.  Adds deny/allow pattern
    lists and optional workspace restriction on top of the security hook
    that ``BoundTool`` already runs.
    """

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = True,
    ) -> None:
        self._timeout = timeout
        self._deny_patterns = (
            deny_patterns if deny_patterns is not None else list(_DEFAULT_DENY_PATTERNS)
        )
        self._allow_patterns = allow_patterns or []
        self._restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "Exec"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command inside the project directory. "
            "Dangerous commands are blocked by deny-pattern guards. "
            "stdout and stderr are returned separately."
        )

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.REQUIRES_APPROVAL

    @property
    def input_schema(self) -> type[ExecInput]:
        return ExecInput

    async def execute(self, input: ExecInput, context: ToolContext) -> ToolResult:
        cwd = str(context.cwd)
        if input.working_dir:
            candidate = Path(input.working_dir).resolve()
            project = context.project_dir.resolve()
            if project not in candidate.parents and candidate != project:
                return ToolResult(
                    content="Blocked: working_dir is outside the project directory.",
                    is_error=True,
                )
            cwd = str(candidate)

        guard_error = self._guard_command(input.command, cwd)
        if guard_error:
            return ToolResult(content=guard_error, is_error=True)

        try:
            proc = await asyncio.create_subprocess_shell(
                input.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
            except TimeoutError:
                proc.kill()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                return ToolResult(
                    content=f"Timeout after {self._timeout}s",
                    is_error=True,
                )

            parts: list[str] = []
            if stdout_bytes:
                parts.append(stdout_bytes.decode("utf-8", errors="replace"))
            if stderr_bytes:
                text = stderr_bytes.decode("utf-8", errors="replace").strip()
                if text:
                    parts.append(f"STDERR:\n{text}")
            if proc.returncode and proc.returncode != 0:
                parts.append(f"\nExit code: {proc.returncode}")

            output = "\n".join(parts) if parts else "(no output)"
            if len(output) > _MAX_OUTPUT_CHARS:
                extra = len(output) - _MAX_OUTPUT_CHARS
                output = output[:_MAX_OUTPUT_CHARS] + f"\n[truncated, {extra} more chars]"

            is_error = proc.returncode is not None and proc.returncode != 0
            return ToolResult(content=output, is_error=is_error)

        except Exception as exc:
            logger.exception("ExecTool error")
            return ToolResult(content=f"Error: {exc}", is_error=True)

    def _guard_command(self, command: str, cwd: str) -> str | None:
        lower = command.strip().lower()

        for pattern in self._deny_patterns:
            if re.search(pattern, lower):
                return "Blocked: command matches a deny pattern."

        if self._allow_patterns and not any(
            re.search(p, lower) for p in self._allow_patterns
        ):
            return "Blocked: command is not in the allow list."

        if self._restrict_to_workspace:
            if "..\\" in command or "../" in command:
                return "Blocked: path traversal detected."

            cwd_path = Path(cwd).resolve()
            for raw in self._extract_absolute_paths(command):
                try:
                    p = Path(raw.strip()).resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Blocked: path outside working directory."

        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        win = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
        posix = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", command)
        return win + posix
