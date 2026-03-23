from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import toml


@dataclass
class ProjectConfigData:
    name: str
    default_branch: str = "main"


@dataclass
class AgentConfigData:
    model: str = "anthropic:claude-sonnet-4-6"
    executor: str = "claude"
    execution_timeout: int = 600


@dataclass
class DatabaseConfigData:
    url: str


@dataclass
class LocalConfig:
    project: ProjectConfigData
    agent: AgentConfigData
    database: DatabaseConfigData


def find_project_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".codeforge" / "config.toml").exists():
            return candidate
    return None


def init_local_config(project_root: Path) -> LocalConfig:
    db_path = (project_root / ".codeforge" / "codeforge.db").resolve()
    return LocalConfig(
        project=ProjectConfigData(name=project_root.name),
        agent=AgentConfigData(),
        database=DatabaseConfigData(url=f"sqlite+aiosqlite:///{db_path}"),
    )


def load_local_config(project_root: Path) -> LocalConfig:
    config_file = project_root / ".codeforge" / "config.toml"
    data = tomllib.loads(config_file.read_text(encoding="utf-8"))
    project_data = data.get("project", {})
    agent_data = data.get("agent", {})
    database_data = data.get("database", {})
    return LocalConfig(
        project=ProjectConfigData(
            name=str(project_data.get("name", project_root.name)),
            default_branch=str(project_data.get("default_branch", "main")),
        ),
        agent=AgentConfigData(
            model=str(agent_data.get("model", "anthropic:claude-sonnet-4-6")),
            executor=str(agent_data.get("executor", "claude")),
            execution_timeout=int(agent_data.get("execution_timeout", 600)),
        ),
        database=DatabaseConfigData(
            url=str(
                database_data.get(
                    "url",
                    f"sqlite+aiosqlite:///{project_root / '.codeforge' / 'codeforge.db'}",
                )
            )
        ),
    )


def save_local_config(project_root: Path, config: LocalConfig) -> None:
    codeforge_dir = project_root / ".codeforge"
    codeforge_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project": {
            "name": config.project.name,
            "default_branch": config.project.default_branch,
        },
        "agent": {
            "model": config.agent.model,
            "executor": config.agent.executor,
            "execution_timeout": config.agent.execution_timeout,
        },
        "database": {
            "url": config.database.url,
        },
    }
    (codeforge_dir / "config.toml").write_text(toml.dumps(payload), encoding="utf-8")
