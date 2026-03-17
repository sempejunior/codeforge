# CodeForge — Contexto para Claude Code

## O que é este projeto

CodeForge é uma plataforma de AI coding autônoma. Um desenvolvedor descreve uma tarefa (ou importa do GitHub/Jira), e o sistema planeja, implementa, revisa e corrige o código automaticamente — tudo em git worktrees isolados, sem tocar a branch principal.

**Referência de arquitetura:** `../Aperant/` (TypeScript/Electron). Adaptamos os padrões para Python/FastAPI com Clean Architecture.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.12+ |
| Web | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async |
| DB | PostgreSQL (prod) / SQLite (dev) |
| Migrations | Alembic |
| AI | LiteLLM (abstração multi-provider) |
| CLI | Typer + Rich |
| Testes | pytest + pytest-asyncio (auto mode) |
| Lint | Ruff |

---

## Arquitetura (Clean Architecture)

```
domain/          ← zero dependências externas (dataclasses puras)
  entities/      ← Task, Spec, ImplementationPlan, QAReport, Agent, Project, Demand, Story, Sprint
  value_objects/ ← TaskId, ProjectId, DemandId, StoryId, SprintId, ModelId, ExecutionPhase, ThinkingLevel, SafeFilePath
  events/        ← DomainEvent base + TaskEvents, AgentEvents, PipelineEvents, DemandEvents, StoryEvents, SprintEvents
  ports/         ← ABCs: AIProviderPort, TaskRepositoryPort, DemandRepositoryPort, StoryRepositoryPort, SprintRepositoryPort, GitServicePort, EventBusPort...
  services/      ← PhaseStateMachine, SubtaskDependencyResolver, complexity_assessor

application/     ← use cases (a implementar)
  use_cases/
  dto/
  services/

infrastructure/  ← adapters concretos
  tools/         ← DefinedTool ABC, BoundTool, 6 tools builtin, ToolRegistry
  security/      ← denylist, command_parser, path_containment, bash_validator, validators/
  config/        ← AGENT_CONFIGS (7 tipos de agente)
  ai/            ← LiteLLMProvider (a implementar)
  persistence/   ← SQLAlchemy repos (a implementar)
  git/           ← GitService (a implementar)
  integrations/  ← GitHub, Jira gateways (a implementar)
  messaging/     ← EventBus in-process (a implementar)

api/             ← FastAPI routes, WebSocket handlers (a implementar)
cli/             ← Typer commands (a implementar)
```

**Regra de dependência:** domain ← application ← infrastructure ← api/cli.
Domain nunca importa nada de fora do próprio domínio.

---

## Convenções de código

- `from __future__ import annotations` em todo arquivo Python
- Type hints em tudo. `X | None` nunca `Optional[X]`
- Dataclasses puras no domain. Pydantic apenas em application/infrastructure
- Async para I/O. Sync para computação pura
- Sem inline comments. Docstrings só onde a intenção não é óbvia
- Sem prints — usar `logging` (stdlib)
- Sem emojis no código
- PascalCase classes, snake_case funções, UPPER_SNAKE_CASE constantes
- Exceções de domínio tipadas, nunca bare `except:`

---

## Sistema de Tools (Phase 2)

Cada tool é um arquivo. Padrão:

```python
class MyTool(DefinedTool):
    @property
    def name(self) -> str: return "MyTool"
    @property
    def permission(self) -> ToolPermission: return ToolPermission.READ_ONLY
    @property
    def input_schema(self) -> type[BaseModel]: return MyInput
    async def execute(self, input: MyInput, context: ToolContext) -> ToolResult: ...
```

`tool.bind(context)` → `BoundTool` que aplica automaticamente:
1. Security hook (via `run_security_hook`) para tools não-ReadOnly
2. Write-path containment (se `context.allowed_write_paths` definido)
3. Safety-net truncation (100 KB) no output

**Tools registradas:** Read, Write, Edit, Bash, Glob, Grep

**Tools por agente** (`AGENT_CONFIGS` em `infrastructure/config/agent_configs.py`):
- `complexity_assessor` → Read, Glob, Grep
- `spec_writer` → Read, Glob, Grep, Write, WebFetch, WebSearch
- `spec_critic` → Read, Glob, Grep, Write
- `planner` → todos
- `coder` → todos
- `qa_reviewer` → Read, Glob, Grep, Write, Edit, Bash (sem web)
- `qa_fixer` → Read, Glob, Grep, Write, Edit, Bash (sem web)

---

## Sistema de Segurança (Phase 2)

Camadas em ordem de execução para o BashTool:

1. **Denylist** (`security/denylist.py`) — 30+ comandos sempre bloqueados (sudo, shutdown, mkfs...)
2. **Validators** por comando (`security/validators/`):
   - `filesystem.py` — rm (bloqueia `/`, `..`, `~`), chmod (bloqueia setuid)
   - `git.py` — bloqueia `git config user.email/name` (identidade)
   - `process.py` — kill/pkill (bloqueia -u, signal -1)
   - `shell.py` — `bash -c 'blocked_cmd'` (anti-bypass recursivo)
   - `database.py` — DROP/TRUNCATE/DELETE sem WHERE em psql/mysql, FLUSHALL em redis
3. **Path containment** (`security/path_containment.py`) — `assert_path_contained()` bloqueia `../` traversal e symlinks que escapam do projeto

---

## Estado dos testes

```
tests/unit/domain/               40 testes  (Phase 1)
  test_phase_state_machine.py    14
  test_subtask_dependency_resolver.py  9
  test_task.py                    8
  test_plan.py                    9

tests/unit/infrastructure/       65 testes  (Phase 2)
  test_security.py               40
  test_tools.py                  25

tests/unit/application/          81 testes  (Phases 3+4)
  test_error_classifier.py       11
  test_prompt_builder.py          5
  test_run_agent_session.py       8
  test_spec_pipeline.py          18
  test_qa_loop.py                12
  test_execute_subtasks.py       14
  test_build_pipeline.py         13

tests/unit/domain/ (extras pós-review)
  test_complexity_assessor.py     7
  test_safe_file_path.py          9

tests/unit/infrastructure/ (extras pós-review)
  test_security.py               53  (13 novos)

tests/unit/domain/ (Phase 5B — novas entidades)
  test_demand.py                 11
  test_story.py                  11
  test_sprint.py                 13
  test_task_v5b.py               14

Total: 258 testes, 0 falhas
```

Rodar: `python -m pytest tests/ -v`

---

## Fases de implementação

| Fase | Status | Descrição |
|------|--------|-----------|
| 1 | COMPLETA | Domain layer (entities, value objects, events, ports, services) |
| 2 | COMPLETA | Tools + Security + Agent config registry |
| 3 | COMPLETA | AI Provider (LiteLLM) + Agent Session loop |
| 4 | COMPLETA | Pipelines (Spec, Build, QA) |
| 5B | COMPLETA | Domain: Demand, Story, Sprint + Task/Project updates |
| 5 | PENDENTE | Persistence (SQLAlchemy) + FastAPI |
| 6 | PENDENTE | CLI (Typer + Rich) |
| 7 | PENDENTE | Git worktrees + GitHub/Jira integrations |
| 8 | PENDENTE | Dashboard React |

---

## Features roadmap notáveis

- **Jira agêntico** (fase 7+): worker que consulta board via JQL e cria tasks automaticamente.
  `TaskSource.JIRA_EPIC` e `IntegrationGatewayPort` já existem no domínio.
- **WebFetch/WebSearch tools** (fase 3): usados por planner e coder para pesquisa
- **Parallel executor** (fase 4): até 3 subtasks simultâneas com backoff exponencial
- **Context window continuation** (fase 3): ao atingir 90% do contexto, sumariza e abre nova sessão
- **Convergence nudge** (fase 3): para qa_reviewer/spec_critic, força conclusão em 75% do step budget
