from __future__ import annotations

BLOCKED_COMMANDS: frozenset[str] = frozenset({
    "shutdown", "reboot", "halt", "poweroff", "init",
    "mkfs", "fdisk", "parted", "gdisk", "dd",
    "sudo", "su", "doas", "chown",
    "iptables", "ip6tables", "nft", "ufw",
    "nmap",
    "systemctl", "service",
    "crontab",
    "mount", "umount",
    "useradd", "userdel", "usermod", "groupadd", "groupdel", "passwd", "visudo",
    # Shell execution primitives — prevent eval/exec bypass and env-prefix injection
    "eval", "exec", "env", "xargs",
})


def is_command_blocked(command: str) -> tuple[bool, str]:
    """Returns (blocked, reason). blocked=True means denied."""
    if command in BLOCKED_COMMANDS:
        return True, f"Command '{command}' is blocked for security reasons."
    return False, ""
