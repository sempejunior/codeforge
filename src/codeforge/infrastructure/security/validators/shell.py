from __future__ import annotations

import shlex

from codeforge.infrastructure.security.command_parser import extract_commands
from codeforge.infrastructure.security.denylist import is_command_blocked


def validate_shell_c(full_segment: str) -> tuple[bool, str]:
    """Validates the inner command of bash/sh -c '...' to prevent denylist bypass."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse shell -c command."

    c_idx = next((i for i, t in enumerate(tokens) if t == "-c"), None)
    if c_idx is None or c_idx + 1 >= len(tokens):
        return True, ""

    inner_command = tokens[c_idx + 1]
    inner_names = extract_commands(inner_command)

    for cmd in inner_names:
        blocked, reason = is_command_blocked(cmd)
        if blocked:
            return False, f"Inner command blocked: {reason}"

    return True, ""
