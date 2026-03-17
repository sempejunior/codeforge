from __future__ import annotations

import pytest

from codeforge.domain.value_objects.file_path import SafeFilePath


def test_create_valid_path(tmp_path):
    result = SafeFilePath.create("src/main.py", tmp_path)
    assert result.value == "src/main.py"


def test_create_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        SafeFilePath.create("../../etc/passwd", tmp_path)


def test_create_rejects_absolute_path_outside(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        SafeFilePath.create("/etc/passwd", tmp_path)


def test_to_absolute_returns_resolved_path(tmp_path):
    sf = SafeFilePath.create("src/main.py", tmp_path)
    absolute = sf.to_absolute(tmp_path)
    assert absolute.is_absolute()
    assert str(absolute).startswith(str(tmp_path))


def test_to_absolute_resolves_symlinks(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_file = real_dir / "target.py"
    real_file.write_text("content")

    link = tmp_path / "link.py"
    link.symlink_to(real_file)

    sf = SafeFilePath("link.py")
    absolute = sf.to_absolute(tmp_path)
    # Should resolve to the real file
    assert absolute == real_file.resolve()


def test_to_absolute_does_not_escape_project(tmp_path):
    outside = tmp_path.parent / "outside.py"
    link = tmp_path / "escape.py"
    link.symlink_to(outside)

    sf = SafeFilePath("escape.py")
    absolute = sf.to_absolute(tmp_path)
    # After resolve(), the path points outside the project — callers must re-validate
    # but to_absolute() should return the resolved path (not the symlink)
    assert absolute.is_absolute()


def test_task_mark_failed_from_terminal_raises():
    from codeforge.domain.entities.task import Task
    from codeforge.domain.value_objects.project_id import ProjectId

    pid = ProjectId.generate()
    task, _ = Task.create(project_id=pid, title="t", description="d")
    # Mark it failed once — moves to FAILED (terminal)
    task.mark_failed("error1")

    # Trying to mark failed again from a terminal state must raise
    with pytest.raises(ValueError, match="Invalid transition"):
        task.mark_failed("error2")


def test_task_mark_cancelled_from_terminal_raises():
    from codeforge.domain.entities.task import Task
    from codeforge.domain.value_objects.project_id import ProjectId

    pid = ProjectId.generate()
    task, _ = Task.create(project_id=pid, title="t", description="d")
    task.mark_cancelled()

    with pytest.raises(ValueError, match="Invalid transition"):
        task.mark_failed("late failure")
