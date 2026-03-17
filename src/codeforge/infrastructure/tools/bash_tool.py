from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 120
_MAX_TIMEOUT_SECONDS = 600
_MAX_OUTPUT_CHARS = 30_000


class BashInput(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(
        default=_DEFAULT_TIMEOUT_SECONDS,
        ge=1,
        le=_MAX_TIMEOUT_SECONDS,
        description="Timeout in seconds",
    )
    run_in_background: bool = Field(
        default=False,
        description="If true, run command in background and return immediately",
    )


class BashTool(DefinedTool):
    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task[tuple[str, bool]]] = set()

    @property
    def name(self) -> str:
        return "Bash"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command in the project directory. "
            "Dangerous commands (sudo, rm /, etc.) are blocked. "
            "Prefer this for running tests, builds, and installs."
        )

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.REQUIRES_APPROVAL

    @property
    def input_schema(self) -> type[BashInput]:
        return BashInput

    async def execute(self, input: BashInput, context: ToolContext) -> ToolResult:
        if input.run_in_background:
            task = asyncio.create_task(self._run(input.command, context.cwd, input.timeout))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return ToolResult(content=f"Background command started: {input.command!r}")

        output, is_error = await self._run(input.command, context.cwd, input.timeout)
        return ToolResult(content=output, is_error=is_error)

    async def _run(
        self, command: str, cwd: Path, timeout: int
    ) -> tuple[str, bool]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(cwd),
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                return f"[Timeout after {timeout}s]: {command!r}", True

            output = stdout.decode("utf-8", errors="replace")
            if len(output) > _MAX_OUTPUT_CHARS:
                output = (
                    output[:_MAX_OUTPUT_CHARS]
                    + f"\n\n[Output truncated at {_MAX_OUTPUT_CHARS} chars]"
                )

            if proc.returncode != 0:
                return output or f"[Exit code {proc.returncode}]", True
            return output, False

        except Exception as exc:
            logger.exception("BashTool error")
            return f"[Error]: {exc}", True
