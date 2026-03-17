from __future__ import annotations

import pytest

from codeforge.infrastructure.security.bash_validator import run_security_hook
from codeforge.infrastructure.security.command_parser import (
    extract_commands,
    split_command_segments,
)
from codeforge.infrastructure.security.denylist import BLOCKED_COMMANDS, is_command_blocked
from codeforge.infrastructure.security.path_containment import (
    PathEscapeError,
    assert_path_contained,
    is_path_contained,
)
from codeforge.infrastructure.security.validators.database import (
    validate_dropdb,
    validate_psql,
    validate_redis_cli,
)
from codeforge.infrastructure.security.validators.filesystem import validate_chmod, validate_rm
from codeforge.infrastructure.security.validators.git import validate_git
from codeforge.infrastructure.security.validators.process import validate_kill, validate_pkill
from codeforge.infrastructure.security.validators.shell import validate_shell_c


def test_blocked_commands_not_empty():
    assert len(BLOCKED_COMMANDS) > 0


def test_sudo_is_blocked():
    blocked, _ = is_command_blocked("sudo")
    assert blocked is True


def test_ls_is_allowed():
    blocked, _ = is_command_blocked("ls")
    assert blocked is False


def test_shutdown_is_blocked():
    blocked, _ = is_command_blocked("shutdown")
    assert blocked is True


def test_pytest_is_allowed():
    blocked, _ = is_command_blocked("pytest")
    assert blocked is False


def test_extract_single_command():
    assert extract_commands("ls -la") == ["ls"]


def test_extract_compound_and():
    names = extract_commands("cd /tmp && ls")
    assert "cd" in names
    assert "ls" in names


def test_extract_compound_semicolon():
    names = extract_commands("echo hello; echo world")
    assert names.count("echo") == 2


def test_split_segments():
    segments = split_command_segments("a && b || c; d")
    assert len(segments) == 4


def test_extract_with_path_prefix():
    names = extract_commands("/usr/bin/python3 script.py")
    assert names == ["python3"]


def test_path_inside_project(tmp_path):
    file = tmp_path / "src" / "main.py"
    file.parent.mkdir()
    file.touch()
    resolved = assert_path_contained("src/main.py", tmp_path)
    assert resolved == file.resolve()


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(PathEscapeError):
        assert_path_contained("../../etc/passwd", tmp_path)


def test_absolute_path_outside_blocked(tmp_path):
    with pytest.raises(PathEscapeError):
        assert_path_contained("/etc/passwd", tmp_path)


def test_is_path_contained_true(tmp_path):
    assert is_path_contained("src/main.py", tmp_path) is True


def test_is_path_contained_false(tmp_path):
    assert is_path_contained("../../etc/passwd", tmp_path) is False


def test_hook_allows_safe_command():
    result = run_security_hook("Bash", {"command": "ls -la"})
    assert result is None


def test_hook_blocks_sudo():
    result = run_security_hook("Bash", {"command": "sudo apt-get install vim"})
    assert result is not None
    assert "sudo" in result.lower() or "blocked" in result.lower()


def test_hook_blocks_shutdown():
    result = run_security_hook("Bash", {"command": "shutdown -h now"})
    assert result is not None


def test_hook_non_bash_tool_skipped():
    result = run_security_hook("Read", {"command": "sudo rm -rf /"})
    assert result is None


def test_hook_allows_pytest():
    result = run_security_hook("Bash", {"command": "python -m pytest tests/"})
    assert result is None


def test_hook_blocks_rm_root():
    result = run_security_hook("Bash", {"command": "rm -rf /"})
    assert result is not None


def test_hook_compound_command_blocked():
    result = run_security_hook("Bash", {"command": "echo hello && sudo reboot"})
    assert result is not None


def test_rm_root_blocked():
    allowed, _ = validate_rm("rm -rf /")
    assert allowed is False


def test_rm_safe_file_allowed():
    allowed, _ = validate_rm("rm -f /tmp/test.txt")
    assert allowed is True


def test_rm_no_preserve_root_blocked():
    allowed, _ = validate_rm("rm --no-preserve-root -rf /")
    assert allowed is False


def test_chmod_setuid_blocked():
    allowed, _ = validate_chmod("chmod 4755 /usr/bin/something")
    assert allowed is False


def test_chmod_normal_allowed():
    allowed, _ = validate_chmod("chmod 755 script.sh")
    assert allowed is True


def test_git_config_email_blocked():
    allowed, _ = validate_git("git config user.email attacker@evil.com")
    assert allowed is False


def test_git_config_name_blocked():
    allowed, _ = validate_git("git config user.name 'Hacker'")
    assert allowed is False


def test_git_commit_allowed():
    allowed, _ = validate_git("git commit -m 'feat: add feature'")
    assert allowed is True


def test_git_push_allowed():
    allowed, _ = validate_git("git push origin main")
    assert allowed is True


def test_kill_signal_1_blocked():
    allowed, _ = validate_kill("kill -1 1")
    assert allowed is False


def test_kill_normal_allowed():
    allowed, _ = validate_kill("kill 12345")
    assert allowed is True


def test_pkill_by_user_blocked():
    allowed, _ = validate_pkill("pkill -u root")
    assert allowed is False


def test_pkill_normal_allowed():
    allowed, _ = validate_pkill("pkill myprocess")
    assert allowed is True


def test_shell_c_blocks_inner_sudo():
    allowed, _ = validate_shell_c("bash -c 'sudo rm -rf /'")
    assert allowed is False


def test_shell_c_allows_safe_inner():
    allowed, _ = validate_shell_c("bash -c 'echo hello'")
    assert allowed is True


def test_psql_drop_blocked():
    allowed, _ = validate_psql("psql -c 'DROP TABLE users'")
    assert allowed is False


def test_psql_select_allowed():
    allowed, _ = validate_psql("psql -c 'SELECT * FROM users'")
    assert allowed is True


def test_redis_flushall_blocked():
    allowed, _ = validate_redis_cli("redis-cli FLUSHALL")
    assert allowed is False


def test_redis_get_allowed():
    allowed, _ = validate_redis_cli("redis-cli GET mykey")
    assert allowed is True


def test_dropdb_prod_blocked():
    allowed, _ = validate_dropdb("dropdb production_db")
    assert allowed is False


def test_dropdb_test_allowed():
    allowed, _ = validate_dropdb("dropdb test_myapp")
    assert allowed is True


# ── New tests covering review fixes ──────────────────────────────────────────


def test_eval_is_blocked():
    blocked, _ = is_command_blocked("eval")
    assert blocked is True


def test_exec_is_blocked():
    blocked, _ = is_command_blocked("exec")
    assert blocked is True


def test_env_is_blocked():
    blocked, _ = is_command_blocked("env")
    assert blocked is True


def test_xargs_is_blocked():
    blocked, _ = is_command_blocked("xargs")
    assert blocked is True


def test_hook_blocks_eval():
    result = run_security_hook("Bash", {"command": "eval 'sudo rm -rf /'"})
    assert result is not None


def test_git_config_global_email_blocked():
    allowed, _ = validate_git("git config --global user.email attacker@evil.com")
    assert allowed is False


def test_git_config_system_name_blocked():
    allowed, _ = validate_git("git config --system user.name hacker")
    assert allowed is False


def test_kill_sigkill_blocked():
    allowed, _ = validate_kill("kill -SIGKILL 1234")
    assert allowed is False


def test_kill_sigterm_blocked():
    allowed, _ = validate_kill("kill -SIGTERM 1234")
    assert allowed is False


def test_kill_sigstop_blocked():
    allowed, _ = validate_kill("kill -SIGSTOP 1234")
    assert allowed is False


def test_psql_file_flag_blocked():
    allowed, _ = validate_psql("psql -f /tmp/dangerous.sql")
    assert allowed is False


def test_psql_file_long_flag_blocked():
    allowed, _ = validate_psql("psql --file /tmp/dangerous.sql")
    assert allowed is False
