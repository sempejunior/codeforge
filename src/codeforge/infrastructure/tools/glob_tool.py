from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
)
from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

_MAX_RESULTS = 2_000
_EXCLUDED_DIRS = frozenset({"node_modules", ".git", "__pycache__", ".venv", "venv", ".mypy_cache"})


class GlobInput(BaseModel):
    pattern: str = Field(description="Glob pattern to match, e.g. '**/*.py'")
    path: str = Field(default=".", description="Directory to search in (relative to project root)")


class GlobTool(DefinedTool):
    @property
    def name(self) -> str:
        return "Glob"

    @property
    def description(self) -> str:
        return "Find files matching a glob pattern, sorted by modification time (newest first)."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def input_schema(self) -> type[GlobInput]:
        return GlobInput

    async def execute(self, input: GlobInput, context: ToolContext) -> ToolResult:
        try:
            search_dir = assert_path_contained(input.path, context.project_dir)
        except PathEscapeError as exc:
            return ToolResult(content=str(exc), is_error=True)

        if not search_dir.is_dir():
            return ToolResult(content=f"Directory not found: {input.path!r}", is_error=True)

        try:
            matches = [
                p for p in search_dir.rglob(input.pattern)
                if not any(part in _EXCLUDED_DIRS for part in p.parts)
            ]
        except Exception as exc:
            return ToolResult(content=f"Glob error: {exc}", is_error=True)

        matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

        truncated = False
        if len(matches) > _MAX_RESULTS:
            matches = matches[:_MAX_RESULTS]
            truncated = True

        lines = [str(p.relative_to(context.project_dir)) for p in matches]
        output = "\n".join(lines)
        if truncated:
            output += f"\n\n[Results truncated at {_MAX_RESULTS} files]"
        if not lines:
            output = f"No files found matching {input.pattern!r}"

        return ToolResult(content=output)
