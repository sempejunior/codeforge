from __future__ import annotations

import re

from codeforge.domain.entities.agent import SessionOutcome

_RATE_LIMIT_PATTERNS: tuple[str, ...] = (
    "rate limit",
    "ratelimit",
    "too many requests",
    "rate_limit_exceeded",
    "requests per minute",
)

_AUTH_PATTERNS: tuple[str, ...] = (
    "unauthorized",
    "authentication",
    "invalid api key",
    "api key not found",
    "token expired",
    "does not have access",
    "permission denied",
    "forbidden",
)

_BILLING_PATTERNS: tuple[str, ...] = (
    "insufficient balance",
    "please recharge",
    "quota exceeded",
    "billing",
    "payment required",
)

_API_KEY_RE = re.compile(
    r"(sk-[a-zA-Z0-9\-]{10,}|Bearer\s+[a-zA-Z0-9\-_.]{10,}|token=[a-zA-Z0-9\-_.]{10,})"
)


def classify_error(exc: Exception) -> tuple[SessionOutcome, str]:
    """Classifies an exception into a SessionOutcome.

    Returns (outcome, sanitized_message). Billing is checked before rate limit
    because some providers return HTTP 429 for billing errors.
    """
    raw_msg = str(exc).lower()
    sanitized = _sanitize_message(str(exc))
    status_code = _extract_status_code(str(exc))

    if any(p in raw_msg for p in _BILLING_PATTERNS):
        return SessionOutcome.ERROR, sanitized

    if status_code == 429 or any(p in raw_msg for p in _RATE_LIMIT_PATTERNS):
        return SessionOutcome.RATE_LIMITED, sanitized

    if status_code == 401 or any(p in raw_msg for p in _AUTH_PATTERNS):
        return SessionOutcome.AUTH_FAILURE, sanitized

    return SessionOutcome.ERROR, sanitized


def _sanitize_message(message: str) -> str:
    return _API_KEY_RE.sub("***", message)


def _extract_status_code(message: str) -> int | None:
    m = re.search(r"(?:status[_\s]code[:\s]+|HTTP\s+)(\d{3})", message, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def is_retryable(outcome: SessionOutcome) -> bool:
    return outcome in (SessionOutcome.RATE_LIMITED, SessionOutcome.AUTH_FAILURE)
