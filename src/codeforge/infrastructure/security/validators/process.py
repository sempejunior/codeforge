from __future__ import annotations

import shlex

_BLOCKED_PROCESS_NAMES: frozenset[str] = frozenset({
    "systemd", "launchd", "init", "sshd",
    "codeforge",
})


def validate_kill(full_segment: str) -> tuple[bool, str]:
    """Blocks dangerous kill signal combinations."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse kill command."

    dangerous_signals = {"-KILL", "-9", "-1", "-0", "-SIGKILL", "-SIGTERM", "-SIGSTOP", "-SIGHUP"}
    dangerous_pids = {"0"}
    for token in tokens[1:]:
        if token in dangerous_signals or token in dangerous_pids:
            return False, f"kill {token!r} is not allowed."
    return True, ""


def validate_pkill(full_segment: str) -> tuple[bool, str]:
    """Blocks pkill -u and killing protected processes."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse pkill command."

    if "-u" in tokens or "--uid" in tokens:
        return False, "pkill -u (kill by user) is not allowed."

    for token in tokens[1:]:
        if not token.startswith("-") and token in _BLOCKED_PROCESS_NAMES:
            return False, f"Killing process {token!r} is not allowed."

    return True, ""
