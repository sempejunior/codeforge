from __future__ import annotations

import re
import shlex

_SEGMENT_SEPARATORS = re.compile(r"&&|\|\||;")
_COMMAND_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-./]+")


def split_command_segments(command: str) -> list[str]:
    """Splits a compound shell command into individual segments."""
    return [s.strip() for s in _SEGMENT_SEPARATORS.split(command) if s.strip()]


def extract_commands(command: str) -> list[str]:
    """Extracts command names from a shell command string using shlex."""
    names: list[str] = []
    for segment in split_command_segments(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = _fallback_extract(segment)
        if tokens:
            names.append(tokens[0].split("/")[-1])
    return names


def _fallback_extract(segment: str) -> list[str]:
    m = _COMMAND_NAME_RE.match(segment.strip())
    if m:
        return [m.group(0).split("/")[-1]]
    return []


def get_full_segment_for(command_name: str, full_command: str) -> str:
    """Returns the full segment that contains the given command name."""
    for segment in split_command_segments(full_command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = _fallback_extract(segment)
        if tokens and tokens[0].split("/")[-1] == command_name:
            return segment
    return full_command
