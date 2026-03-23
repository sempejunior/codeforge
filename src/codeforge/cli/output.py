from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codeforge.application.use_cases.run_code_review import CodeReviewReport
from codeforge.domain.entities.project import Project
from codeforge.domain.entities.task import Task


def render_projects(console: Console, projects: list[Project]) -> None:
    table = Table(title="Projetos")
    table.add_column("ID", style="cyan")
    table.add_column("Nome")
    table.add_column("Team")
    for project in projects:
        table.add_row(
            str(project.id)[:8],
            project.name,
            str(project.team_id)[:8] if project.team_id else "-",
        )
    console.print(table)


def render_tasks(console: Console, tasks: list[Task]) -> None:
    table = Table(title="Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Titulo")
    table.add_column("Status")
    table.add_column("Assignee")
    for task in tasks:
        table.add_row(str(task.id)[:8], task.title, task.status.value, task.assignee_type.value)
    console.print(table)


def render_diff_summary(console: Console, changed_files: list[str], diff: str) -> None:
    lines = [f"- {path}" for path in changed_files] or ["- Nenhum arquivo alterado detectado"]
    preview = diff[:3000] if diff else "Sem diff disponivel"
    console.print(Panel("\n".join(lines), title="Arquivos alterados"))
    console.print(Panel(preview, title="Diff (preview)"))


def render_review(console: Console, report: CodeReviewReport) -> None:
    header = f"Verdict: {report.verdict}\n\n{report.summary}"
    console.print(Panel(header, title="Code Review"))
    if not report.issues:
        return
    table = Table(title="Issues")
    table.add_column("Severidade")
    table.add_column("Titulo")
    table.add_column("Arquivo")
    for issue in report.issues:
        table.add_row(issue.severity, issue.title, issue.file_path or "-")
    console.print(table)
