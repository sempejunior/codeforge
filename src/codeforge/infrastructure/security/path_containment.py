from __future__ import annotations

from pathlib import Path


class PathEscapeError(Exception):
    pass


def assert_path_contained(file_path: str | Path, project_dir: str | Path) -> Path:
    """Resolves file_path and asserts it is inside project_dir.

    Returns the resolved absolute path.
    Raises PathEscapeError if the path would escape the project root.
    """
    root = Path(project_dir).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    resolved = target.resolve()

    if resolved != root and not str(resolved).startswith(str(root) + "/"):
        raise PathEscapeError(
            f"Path {str(file_path)!r} resolves to {str(resolved)!r} "
            f"which is outside the project root {str(root)!r}."
        )
    return resolved


def is_path_contained(file_path: str | Path, project_dir: str | Path) -> bool:
    try:
        assert_path_contained(file_path, project_dir)
        return True
    except PathEscapeError:
        return False
