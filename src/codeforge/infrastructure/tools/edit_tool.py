from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
)
from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class EditInput(BaseModel):
    file_path: str = Field(description="File to edit")
    old_string: str = Field(description="Exact string to replace")
    new_string: str = Field(description="Replacement string")
    replace_all: bool = Field(default=False, description="Replace all occurrences")


class EditTool(DefinedTool):
    @property
    def name(self) -> str:
        return "Edit"

    @property
    def description(self) -> str:
        return (
            "Perform an exact string replacement in a file. "
            "The old_string must appear exactly once unless replace_all=true."
        )

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.REQUIRES_APPROVAL

    @property
    def input_schema(self) -> type[EditInput]:
        return EditInput

    async def execute(self, input: EditInput, context: ToolContext) -> ToolResult:
        path_str = input.file_path.rstrip("'\"}")

        try:
            resolved = assert_path_contained(path_str, context.project_dir)
        except PathEscapeError as exc:
            return ToolResult(content=str(exc), is_error=True)

        if not resolved.exists():
            return ToolResult(content=f"File not found: {path_str!r}", is_error=True)

        if input.old_string == input.new_string:
            return ToolResult(
                content="old_string and new_string are identical -- nothing to do.", is_error=True
            )

        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        count = content.count(input.old_string)
        if count == 0:
            return ToolResult(content=f"old_string not found in {path_str!r}.", is_error=True)
        if count > 1 and not input.replace_all:
            return ToolResult(
                content=(
                    f"old_string appears {count} times in {path_str!r}. "
                    "Provide more context to make it unique, or use replace_all=true."
                ),
                is_error=True,
            )

        if input.replace_all:
            new_content = content.replace(input.old_string, input.new_string)
        else:
            idx = content.index(input.old_string)
            new_content = content[:idx] + input.new_string + content[idx + len(input.old_string) :]

        try:
            resolved.write_text(new_content, encoding="utf-8")
            replaced = count if input.replace_all else 1
            return ToolResult(content=f"Replaced {replaced} occurrence(s) in {path_str!r}")
        except OSError as exc:
            return ToolResult(content=f"Write failed: {exc}", is_error=True)
