from __future__ import annotations

from ..value_objects.complexity import ComplexityTier

_COMPLEX_KEYWORDS = frozenset({
    "authentication", "authorization", "oauth", "migration", "database",
    "refactor", "architecture", "distributed", "concurrent", "async",
    "microservice", "api", "integration", "security", "payment",
})

_SIMPLE_KEYWORDS = frozenset({
    "fix typo", "update readme", "rename", "move file", "delete",
    "add comment", "format", "lint",
})


def assess_complexity_heuristic(title: str, description: str) -> ComplexityTier:
    """Heuristic complexity assessment used as fallback when LLM assessment fails."""
    text = f"{title} {description}".lower()
    word_count = len(description.split())

    if any(kw in text for kw in _SIMPLE_KEYWORDS) and word_count < 50:
        return ComplexityTier.SIMPLE

    if any(kw in text for kw in _COMPLEX_KEYWORDS):
        return ComplexityTier.COMPLEX

    if word_count > 200:
        return ComplexityTier.COMPLEX

    if word_count < 30:
        return ComplexityTier.SIMPLE

    return ComplexityTier.STANDARD
