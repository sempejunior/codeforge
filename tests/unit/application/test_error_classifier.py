from __future__ import annotations

from codeforge.domain.entities.agent import SessionOutcome
from codeforge.infrastructure.security.error_classifier import classify_error, is_retryable


def test_rate_limit_by_status_code():
    exc = Exception("HTTP 429: Too Many Requests")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.RATE_LIMITED


def test_rate_limit_by_message():
    exc = Exception("rate limit exceeded")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.RATE_LIMITED


def test_auth_failure_401():
    exc = Exception("HTTP 401: Unauthorized")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.AUTH_FAILURE


def test_auth_failure_by_message():
    exc = Exception("invalid api key provided")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.AUTH_FAILURE


def test_billing_before_rate_limit():
    exc = Exception("HTTP 429: insufficient balance, please recharge")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.ERROR


def test_generic_error():
    exc = Exception("connection timeout")
    outcome, _ = classify_error(exc)
    assert outcome == SessionOutcome.ERROR


def test_sanitizes_api_key():
    exc = Exception("invalid key: sk-ant-api03-abcdefghijklmnop")
    _, msg = classify_error(exc)
    assert "sk-ant" not in msg
    assert "***" in msg


def test_rate_limited_is_retryable():
    assert is_retryable(SessionOutcome.RATE_LIMITED) is True


def test_auth_failure_is_retryable():
    assert is_retryable(SessionOutcome.AUTH_FAILURE) is True


def test_error_not_retryable():
    assert is_retryable(SessionOutcome.ERROR) is False


def test_completed_not_retryable():
    assert is_retryable(SessionOutcome.COMPLETED) is False
