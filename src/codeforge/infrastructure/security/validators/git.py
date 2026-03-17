from __future__ import annotations

import shlex

_BLOCKED_GIT_CONFIG_KEYS: frozenset[str] = frozenset({
    "user.name", "user.email",
    "author.name", "author.email",
    "committer.name", "committer.email",
})


def validate_git(full_segment: str) -> tuple[bool, str]:
    """Blocks git config overrides for identity fields."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse git command."

    if "config" in tokens:
        idx = tokens.index("config")
        # Scan all tokens after "config", skipping flags (--global, --system, --local, etc.)
        for token in tokens[idx + 1 :]:
            if token in _BLOCKED_GIT_CONFIG_KEYS:
                return False, f"git config {token!r} override is not allowed."

    for token in tokens:
        if token.startswith("-c"):
            value = token[2:].strip().lstrip("=")
            for key in _BLOCKED_GIT_CONFIG_KEYS:
                if value.startswith(key + "=") or value == key:
                    return False, f"git -c override of {key!r} is not allowed."

    return True, ""
