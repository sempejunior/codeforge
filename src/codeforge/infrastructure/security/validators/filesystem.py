from __future__ import annotations

import shlex

_DANGEROUS_RM_PATTERNS: frozenset[str] = frozenset({
    "/", "..", "~", "*", "/*", "../", "/home", "/usr",
    "/etc", "/var", "/bin", "/lib", "/opt", "/root",
})


def validate_rm(full_segment: str) -> tuple[bool, str]:
    """Returns (allowed, reason). allowed=False means blocked."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse rm command."

    if "--no-preserve-root" in tokens:
        return False, "rm --no-preserve-root is not allowed."

    paths = [t for t in tokens[1:] if not t.startswith("-")]
    for path in paths:
        if path in _DANGEROUS_RM_PATTERNS:
            return False, f"Removing {path!r} is not allowed."
    return True, ""


def validate_chmod(full_segment: str) -> tuple[bool, str]:
    """Blocks setuid/setgid mode bits."""
    try:
        tokens = shlex.split(full_segment)
    except ValueError:
        return False, "Could not parse chmod command."

    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        if "+s" in token or (token.startswith(("4", "2", "6")) and len(token) >= 4):
            return False, f"chmod mode {token!r} sets setuid/setgid bits, which is not allowed."
    return True, ""
