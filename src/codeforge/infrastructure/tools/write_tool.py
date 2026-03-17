from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
)
from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class WriteInput(BaseModel):
    file_path: str = Field(description="Path to write (relative to project root or absolute)")
    content: str = Field(description="File content to write")


class WriteTool(DefinedTool):
    @property
    def name(self) -> str:
        return "Write"

    @property
    def description(self) -> str:
        return "Write content to a file, creating parent directories as needed."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.REQUIRES_APPROVAL

    @property
    def input_schema(self) -> type[WriteInput]:
        return WriteInput

    async def execute(self, input: WriteInput, context: ToolContext) -> ToolResult:
        path_str = input.file_path.rstrip("'\"}")

        try:
            resolved = assert_path_contained(path_str, context.project_dir)
        except PathEscapeError as exc:
            return ToolResult(content=str(exc), is_error=True)

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(input.content, encoding="utf-8")
            lines = input.content.count("\n") + 1
            return ToolResult(content=f"Successfully wrote {lines} lines to {path_str!r}")
        except OSError as exc:
            return ToolResult(content=f"Write failed: {exc}", is_error=True)
