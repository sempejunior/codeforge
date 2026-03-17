from __future__ import annotations

import logging

from codeforge.domain.entities.agent import AgentType
from codeforge.infrastructure.tools.base import BoundTool, DefinedTool, ToolContext

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry of all available tools, keyed by name."""

    def __init__(self) -> None:
        self._tools: dict[str, DefinedTool] = {}

    def register(self, tool: DefinedTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> DefinedTool | None:
        return self._tools.get(name)

    def registered_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_tools_for_agent(
        self, agent_type: AgentType, context: ToolContext
    ) -> dict[str, BoundTool]:
        """Returns BoundTools filtered by the agent type's allowed tool set."""
        from codeforge.infrastructure.config.agent_configs import AGENT_CONFIGS

        config = AGENT_CONFIGS.get(agent_type)
        if config is None:
            logger.warning("No config for agent type %r -- returning empty tool set.", agent_type)
            return {}

        result: dict[str, BoundTool] = {}
        for name in config.tools:
            tool = self._tools.get(name)
            if tool is None:
                logger.debug("Tool %r configured for %r but not registered.", name, agent_type)
                continue
            result[name] = tool.bind(context)
        return result


def build_default_registry() -> ToolRegistry:
    """Creates a ToolRegistry pre-populated with all builtin tools."""
    from codeforge.infrastructure.tools.bash_tool import BashTool
    from codeforge.infrastructure.tools.edit_tool import EditTool
    from codeforge.infrastructure.tools.glob_tool import GlobTool
    from codeforge.infrastructure.tools.grep_tool import GrepTool
    from codeforge.infrastructure.tools.read_tool import ReadTool
    from codeforge.infrastructure.tools.write_tool import WriteTool

    registry = ToolRegistry()
    for tool in [ReadTool(), WriteTool(), EditTool(), BashTool(), GlobTool(), GrepTool()]:
        registry.register(tool)
    return registry
