from __future__ import annotations

import re
import shlex

_DANGEROUS_SQL_PATTERNS = re.compile(
    r"\b(DROP\s+(DATABASE|TABLE|INDEX|SCHEMA|VIEW|SEQUENCE)"
    r"|TRUNCATE"
    r"|DELETE\s+FROM\s+\w+\s*(?!WHERE))\b",
    re.IGNORECASE,
)

_SAFE_DB_NAME_RE = re.compile(
    r"^(test|dev|local|tmp|temp|scratch|sandbox|mock)[-_]?", re.IGNORECASE
)

_REDIS_BLOCKED: frozenset[str] = frozenset({
    "FLUSHALL", "FLUSHDB", "DEBUG", "SHUTDOWN",
    "CONFIG", "CLUSTER", "SLAVEOF", "REPLICAOF",
})


def validate_psql(full_segment: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse psql command."
    for i, token in enumerate(tokens):
        if token in ("-f", "--file"):
            return False, "psql -f (execute SQL file) is not allowed."
        if (
            token == "-c"
            and i + 1 < len(tokens)
            and _DANGEROUS_SQL_PATTERNS.search(tokens[i + 1])
        ):
            return False, "Dangerous SQL in psql -c is not allowed."
    return True, ""


def validate_mysql(full_segment: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse mysql command."
    for i, token in enumerate(tokens):
        if (
            token in ("-e", "--execute")
            and i + 1 < len(tokens)
            and _DANGEROUS_SQL_PATTERNS.search(tokens[i + 1])
        ):
            return False, "Dangerous SQL in mysql -e is not allowed."
    return True, ""


def validate_redis_cli(full_segment: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse redis-cli command."
    for token in tokens[1:]:
        if token.upper() in _REDIS_BLOCKED:
            return False, f"redis-cli command {token!r} is not allowed."
    return True, ""


def validate_dropdb(full_segment: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse dropdb command."
    db_names = [t for t in tokens[1:] if not t.startswith("-")]
    for name in db_names:
        if not _SAFE_DB_NAME_RE.match(name):
            return False, f"dropdb on database {name!r} is only allowed for test/dev databases."
    return True, ""
