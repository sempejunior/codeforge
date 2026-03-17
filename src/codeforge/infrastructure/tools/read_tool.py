from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
)
from codeforge.infrastructure.tools.base import DefinedTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

_MAX_LINES = 2_000
_MAX_LINE_CHARS = 2_000
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"})


class ReadInput(BaseModel):
    file_path: str = Field(
        description="Path to file to read (relative to project root or absolute)"
    )
    offset: int = Field(
        default=0, ge=0, description="Line offset to start reading from (1-based, 0 = start)"
    )
    limit: int = Field(default=_MAX_LINES, ge=1, le=_MAX_LINES, description="Max lines to read")


class ReadTool(DefinedTool):
    @property
    def name(self) -> str:
        return "Read"

    @property
    def description(self) -> str:
        return "Read the contents of a file. Returns file contents with line numbers."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def input_schema(self) -> type[ReadInput]:
        return ReadInput

    async def execute(self, input: ReadInput, context: ToolContext) -> ToolResult:
        path_str = input.file_path.rstrip("'\"}")

        try:
            resolved = assert_path_contained(path_str, context.project_dir)
        except PathEscapeError as exc:
            return ToolResult(content=str(exc), is_error=True)

        if resolved.suffix.lower() in _IMAGE_EXTENSIONS:
            return await self._read_image(resolved)

        if not resolved.exists():
            return ToolResult(content=f"File not found: {path_str!r}", is_error=True)

        if not resolved.is_file():
            return ToolResult(content=f"{path_str!r} is not a file.", is_error=True)

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(content=f"Cannot read file: {exc}", is_error=True)

        all_lines = content.splitlines()
        total = len(all_lines)
        start = max(0, input.offset - 1) if input.offset > 0 else 0
        end = min(start + input.limit, total)
        selected = all_lines[start:end]

        lines_out: list[str] = []
        for i, line in enumerate(selected, start=start + 1):
            if len(line) > _MAX_LINE_CHARS:
                line = line[:_MAX_LINE_CHARS] + " ... (truncated)"
            lines_out.append(f"{i:6}\t{line}")

        rel = resolved.relative_to(context.project_dir)
        header = f"[{rel} -- lines {start + 1}-{end} of {total}]\n"
        return ToolResult(content=header + "\n".join(lines_out))

    async def _read_image(self, path: Path) -> ToolResult:
        import base64
        import mimetypes

        mime, _ = mimetypes.guess_type(str(path))
        if not mime:
            mime = "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return ToolResult(content=f"data:{mime};base64,{data}")
