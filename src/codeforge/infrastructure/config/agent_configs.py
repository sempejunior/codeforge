from __future__ import annotations

from codeforge.domain.entities.agent import AgentConfig, AgentType
from codeforge.domain.value_objects.thinking_level import ThinkingLevel

_BASE_READ: frozenset[str] = frozenset({"Read", "Glob", "Grep"})
_BASE_WRITE: frozenset[str] = frozenset({"Write", "Edit", "Bash"})
_WEB: frozenset[str] = frozenset({"WebFetch", "WebSearch"})
_ALL: frozenset[str] = _BASE_READ | _BASE_WRITE | _WEB
_SPEC: frozenset[str] = _BASE_READ | {"Write"} | _WEB
_QA: frozenset[str] = _BASE_READ | _BASE_WRITE

AGENT_CONFIGS: dict[AgentType, AgentConfig] = {
    AgentType.COMPLEXITY_ASSESSOR: AgentConfig(
        tools=_BASE_READ,
        thinking_level=ThinkingLevel.MEDIUM,
        max_steps=50,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=None,
    ),
    AgentType.SPEC_WRITER: AgentConfig(
        tools=_SPEC,
        thinking_level=ThinkingLevel.HIGH,
        max_steps=150,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=None,
    ),
    AgentType.SPEC_CRITIC: AgentConfig(
        tools=_BASE_READ | {"Write"},
        thinking_level=ThinkingLevel.HIGH,
        max_steps=100,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=0.80,
    ),
    AgentType.PLANNER: AgentConfig(
        tools=_ALL,
        thinking_level=ThinkingLevel.HIGH,
        max_steps=200,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=None,
    ),
    AgentType.CODER: AgentConfig(
        tools=_ALL,
        thinking_level=ThinkingLevel.MEDIUM,
        max_steps=1_000,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=None,
    ),
    AgentType.QA_REVIEWER: AgentConfig(
        tools=_QA,
        thinking_level=ThinkingLevel.HIGH,
        max_steps=300,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=0.75,
    ),
    AgentType.QA_FIXER: AgentConfig(
        tools=_QA,
        thinking_level=ThinkingLevel.MEDIUM,
        max_steps=400,
        context_window_warning_pct=0.85,
        context_window_abort_pct=0.90,
        convergence_nudge_pct=None,
    ),
}
