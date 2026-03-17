from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_MAX_OUTPUT_BYTES = 100_000
_MAX_OUTPUT_LINES = 2_000


class ToolPermission(StrEnum):
    READ_ONLY = "read_only"
    AUTO = "auto"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class ToolContext:
    cwd: Path
    project_dir: Path
    spec_dir: Path | None = None
    abort_event: Any | None = None
    allowed_write_paths: list[Path] | None = None


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


def truncate_output(output: str, max_bytes: int = _MAX_OUTPUT_BYTES) -> str:
    """Truncates tool output if it exceeds size limits."""
    lines = output.splitlines()
    if len(lines) > _MAX_OUTPUT_LINES:
        truncated = "\n".join(lines[:_MAX_OUTPUT_LINES])
        truncated += (
            f"\n\n[Output truncated: showing first"
            f" {_MAX_OUTPUT_LINES} of {len(lines)} lines]"
        )
        return truncated
    encoded = output.encode("utf-8")
    if len(encoded) <= max_bytes:
        return output
    # Decode with errors="ignore" to avoid splitting multi-byte codepoints
    truncated_bytes = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated_bytes + f"\n\n[Output truncated at {max_bytes} bytes]"


class DefinedTool(ABC):
    """Base class for all agent tools."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def permission(self) -> ToolPermission: ...

    @property
    @abstractmethod
    def input_schema(self) -> type[BaseModel]: ...

    @abstractmethod
    async def execute(self, input: BaseModel, context: ToolContext) -> ToolResult: ...

    def bind(self, context: ToolContext) -> BoundTool:
        return BoundTool(tool=self, context=context)


@dataclass
class BoundTool:
    """A tool bound to a specific ToolContext, ready to be passed to the LLM."""

    tool: DefinedTool
    context: ToolContext

    @property
    def name(self) -> str:
        return self.tool.name

    @property
    def description(self) -> str:
        return self.tool.description

    @property
    def input_schema(self) -> type[BaseModel]:
        return self.tool.input_schema

    async def __call__(self, **kwargs: Any) -> str:
        from codeforge.infrastructure.security.bash_validator import run_security_hook

        input_obj = self.tool.input_schema(**kwargs)

        if self.tool.permission != ToolPermission.READ_ONLY:
            result = run_security_hook(self.tool.name, kwargs)
            if result is not None:
                return f"[BLOCKED] {result}"

            if self.context.allowed_write_paths:
                path_arg = kwargs.get("file_path") or kwargs.get("path")
                if path_arg:
                    target = Path(str(path_arg))
                    if not target.is_absolute():
                        target = self.context.cwd / target
                    allowed = any(
                        str(target.resolve()).startswith(str(p.resolve()))
                        for p in self.context.allowed_write_paths
                    )
                    if not allowed:
                        return f"[BLOCKED] Write to {path_arg!r} is outside allowed write paths."

        tool_result = await self.tool.execute(input_obj, self.context)
        output = tool_result.content
        if not tool_result.is_error:
            output = truncate_output(output)
        return output
