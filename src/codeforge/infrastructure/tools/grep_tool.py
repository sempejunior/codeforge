from __future__ import annotations

import asyncio
import logging
import shutil

from pydantic import BaseModel, Field

from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
)
from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

_MAX_OUTPUT_CHARS = 30_000
_TIMEOUT_SECONDS = 60


class GrepInput(BaseModel):
    pattern: str = Field(description="Regular expression pattern to search")
    path: str = Field(default=".", description="File or directory to search")
    glob: str | None = Field(default=None, description="Glob filter, e.g. '*.py'")
    file_type: str | None = Field(default=None, description="File type filter, e.g. 'py', 'js'")
    output_mode: str = Field(
        default="files_with_matches",
        description="One of: files_with_matches, content, count",
    )
    context_lines: int = Field(
        default=0, ge=0, le=10, description="Lines of context (content mode)"
    )
    case_insensitive: bool = Field(default=False)


class GrepTool(DefinedTool):
    @property
    def name(self) -> str:
        return "Grep"

    @property
    def description(self) -> str:
        return (
            "Search file contents using ripgrep (rg). "
            "Supports regex patterns, file type filters, and context lines."
        )

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def input_schema(self) -> type[GrepInput]:
        return GrepInput

    async def execute(self, input: GrepInput, context: ToolContext) -> ToolResult:
        try:
            search_path = assert_path_contained(input.path, context.project_dir)
        except PathEscapeError as exc:
            return ToolResult(content=str(exc), is_error=True)

        rg = shutil.which("rg")
        if rg is None:
            return await self._python_fallback(input, search_path)

        cmd = self._build_rg_command(rg, input, str(search_path))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_TIMEOUT_SECONDS
            )
        except TimeoutError:
            return ToolResult(content=f"[Grep timed out after {_TIMEOUT_SECONDS}s]", is_error=True)
        except Exception as exc:
            return ToolResult(content=f"[Grep error: {exc}]", is_error=True)

        if proc.returncode == 1:
            return ToolResult(content="No matches found.")
        if proc.returncode and proc.returncode > 1:
            err = stderr.decode("utf-8", errors="replace").strip()
            return ToolResult(content=f"[rg error]: {err}", is_error=True)

        output = stdout.decode("utf-8", errors="replace")
        if len(output) > _MAX_OUTPUT_CHARS:
            output = (
                output[:_MAX_OUTPUT_CHARS]
                + f"\n\n[Output truncated at {_MAX_OUTPUT_CHARS} chars]"
            )
        return ToolResult(content=output or "No matches found.")

    def _build_rg_command(self, rg: str, input: GrepInput, path: str) -> list[str]:
        cmd = [rg, "--no-heading"]
        if input.case_insensitive:
            cmd.append("-i")
        if input.output_mode == "files_with_matches":
            cmd.append("-l")
        elif input.output_mode == "count":
            cmd.append("-c")
        else:
            cmd.append("-n")
            if input.context_lines > 0:
                cmd.extend(["-C", str(input.context_lines)])
        if input.file_type:
            cmd.extend(["--type", input.file_type])
        if input.glob:
            cmd.extend(["--glob", input.glob])
        cmd.extend([input.pattern, path])
        return cmd

    async def _python_fallback(self, input: GrepInput, search_path: object) -> ToolResult:
        """Fallback grep using Python re when rg is not available."""
        import re
        from pathlib import Path

        _EXCLUDED_DIRS = frozenset({
            "node_modules", ".git", "__pycache__", ".venv", "venv", ".mypy_cache"
        })

        try:
            flags = re.IGNORECASE if input.case_insensitive else 0
            compiled = re.compile(input.pattern, flags)
        except re.error as exc:
            return ToolResult(content=f"Invalid regex: {exc}", is_error=True)

        search = Path(str(search_path))
        if search.is_file():
            candidates = [search]
        else:
            candidates = [
                p for p in search.rglob("*")
                if not any(part in _EXCLUDED_DIRS for part in p.parts)
            ]

        matches: list[str] = []
        for f in candidates:
            if not f.is_file():
                continue
            if input.glob and not f.match(input.glob):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if compiled.search(content):
                matches.append(str(f))

        if not matches:
            return ToolResult(content="No matches found.")
        return ToolResult(content="\n".join(matches))
