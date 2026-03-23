from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from codeforge.cli.main import app


def test_codeforge_help_shows_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "project" in result.stdout
    assert "task" in result.stdout
    assert "config" in result.stdout


def test_project_init_creates_config_and_database(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_path = tmp_path / "myproject"

    result = runner.invoke(app, ["project", "init", str(project_path)])

    assert result.exit_code == 0
    assert (project_path / ".codeforge" / "config.toml").exists()
    assert (project_path / ".codeforge" / "codeforge.db").exists()

    monkeypatch.chdir(project_path)
    status = runner.invoke(app, ["project", "status"])
    assert status.exit_code == 0
    assert "Projetos" in status.stdout


def test_task_create_and_list(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    project_path = tmp_path / "repo"

    init_result = runner.invoke(app, ["project", "init", str(project_path)])
    assert init_result.exit_code == 0

    (project_path / ".git").mkdir(exist_ok=True)
    monkeypatch.chdir(project_path)
    created = runner.invoke(
        app,
        [
            "task",
            "create",
            "Implement endpoint",
            "--description",
            "- should add route",
        ],
    )
    assert created.exit_code == 0
    assert "Task criada" in created.stdout

    listed = runner.invoke(app, ["task", "list"])
    assert listed.exit_code == 0
    assert "Implement endpoint" in listed.stdout
