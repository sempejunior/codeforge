from __future__ import annotations

import logging
from typing import Any

from codeforge.infrastructure.security.command_parser import extract_commands, get_full_segment_for
from codeforge.infrastructure.security.denylist import is_command_blocked
from codeforge.infrastructure.security.validators.database import (
    validate_dropdb,
    validate_mysql,
    validate_psql,
    validate_redis_cli,
)
from codeforge.infrastructure.security.validators.filesystem import validate_chmod, validate_rm
from codeforge.infrastructure.security.validators.git import validate_git
from codeforge.infrastructure.security.validators.process import validate_kill, validate_pkill
from codeforge.infrastructure.security.validators.shell import validate_shell_c

logger = logging.getLogger(__name__)

_VALIDATORS: dict[str, Any] = {
    "rm": validate_rm,
    "chmod": validate_chmod,
    "git": validate_git,
    "kill": validate_kill,
    "pkill": validate_pkill,
    "killall": validate_pkill,
    "bash": validate_shell_c,
    "sh": validate_shell_c,
    "zsh": validate_shell_c,
    "psql": validate_psql,
    "mysql": validate_mysql,
    "redis-cli": validate_redis_cli,
    "dropdb": validate_dropdb,
    "dropuser": validate_dropdb,
}


def run_security_hook(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """Runs security validation for the Bash tool.

    Returns an error string if the command should be blocked, None if allowed.
    Only applies to the Bash tool.
    """
    if tool_name != "Bash":
        return None

    command = tool_input.get("command", "")
    if not command or not isinstance(command, str):
        return None

    command_names = extract_commands(command)
    for cmd_name in command_names:
        blocked, reason = is_command_blocked(cmd_name)
        if blocked:
            logger.warning("Blocked command: %s -- %s", cmd_name, reason)
            return reason

        validator = _VALIDATORS.get(cmd_name)
        if validator is not None:
            full_segment = get_full_segment_for(cmd_name, command)
            allowed, reason = validator(full_segment)
            if not allowed:
                logger.warning("Validator blocked %s: %s", cmd_name, reason)
                return reason

    return None
