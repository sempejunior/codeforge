from __future__ import annotations

from codeforge.domain.services.complexity_assessor import assess_complexity_heuristic
from codeforge.domain.value_objects.complexity import ComplexityTier


def test_simple_keyword_with_short_description():
    result = assess_complexity_heuristic("fix typo in README", "Just a small typo fix")
    assert result == ComplexityTier.SIMPLE


def test_complex_keyword_triggers_complex():
    result = assess_complexity_heuristic("add authentication", "Implement OAuth2 login flow")
    assert result == ComplexityTier.COMPLEX


def test_long_description_is_complex():
    long_desc = "word " * 201
    result = assess_complexity_heuristic("add feature", long_desc)
    assert result == ComplexityTier.COMPLEX


def test_very_short_description_is_simple():
    result = assess_complexity_heuristic("update config", "Change timeout")
    assert result == ComplexityTier.SIMPLE


def test_medium_description_is_standard():
    desc = "word " * 50  # 50 words, not short (<30) and not long (>200)
    result = assess_complexity_heuristic("add new endpoint", desc)
    assert result == ComplexityTier.STANDARD


def test_simple_keyword_with_long_desc_not_simple():
    long_desc = "word " * 60
    result = assess_complexity_heuristic("rename variable", long_desc)
    # word_count >= 50, so SIMPLE keyword doesn't trigger simple
    assert result != ComplexityTier.SIMPLE


def test_complexity_tier_from_spec_equals_from_task():
    from codeforge.domain.entities.spec import ComplexityTier as SpecTier
    from codeforge.domain.entities.task import ComplexityTier as TaskTier

    assert SpecTier.SIMPLE == TaskTier.SIMPLE
    assert SpecTier is TaskTier  # same object — no more duplication
