# CodeForge — Fases de Implementação

## Status geral

| Fase | Status | Testes | Descrição |
|------|--------|--------|-----------|
| 1 | ✅ COMPLETA | 40 | Domain layer |
| 2 | ✅ COMPLETA | 65 | Tools + Security |
| 3 | ✅ COMPLETA | 24 | AI Provider + Agent Session |
| 4 | ✅ COMPLETA | 57 | Pipelines de orquestração |
| 5B | ✅ COMPLETA | 45 | Domain: Demand, Story, Sprint |
| 5 | ✅ COMPLETA | 9 | Persistence + API REST |
| 5C | ✅ COMPLETA | 29 | Agent Intelligence Layer |
| 6 | ✅ COMPLETA | 11 | CLI + Execução via Claude Code |
| 7 | ✅ COMPLETA | 10 | Breakdown Agent + GitHub Gateway + Demand Assistant |
| 8 | ✅ COMPLETA | — | Dashboard React (PM + Dev) |
| 9 | ⏳ PENDENTE | — | Time e colaboração |
| 10 | ⏳ PENDENTE | — | Cloud execution (VMs efêmeras) |

**Total atual: 317 testes, 0 falhas**

---

## Contexto de produto — evolução da visão

As fases 1–4 construíram o motor interno: um loop agêntico completo com tools, segurança, provider LLM e pipelines de spec/build/QA. Esse motor continua sendo a base, mas a visão de produto evoluiu de forma importante.

**O CodeForge não é um agent loop concorrente do Claude Code ou Aider. É a camada de PM e orquestração em cima deles.**

A mudança central de arquitetura de execução:

```
Antes (fases 1–4):
  CodeForge → LiteLLM → AI → tools próprias (Read, Write, Bash...)

Depois (fases 6+):
  CodeForge → spawna subprocess → claude / opencode / aider → executa
```

O CodeForge passa a ser responsável por:
- Gestão do produto (demandas, entregáveis, sprints, tasks)
- Breakdown automático (agente que lê o repo e cria tasks com contexto real)
- Orquestração (qual tarefa, para qual executor, em qual repositório)
- Rastreamento (branch criada, commits, PR aberto, testes passando)
- Code review (IA revisa o PR com contexto da task original)
- Human-in-the-loop (aprovações configuráveis em cada etapa)

O motor das fases 1–4 permanece útil para agentes internos (breakdown, code review, demand_assistant) que não precisam editar código — só ler, analisar e escrever relatórios.

**Hipótese central a validar (Fase 6):**
> Se você der ao Claude Code uma task bem descrita com contexto real do repositório, ele produz um resultado bom o suficiente para que o humano só precise revisar, não reescrever.

Tudo que vem depois depende dessa hipótese ser verdade.

---

## Fase 1 — Domain Layer ✅

**Objetivo:** Construir o núcleo do domínio completamente isolado de frameworks externos. Zero dependências de SQLAlchemy, Pydantic, FastAPI, LiteLLM.

### O que foi implementado

**Value Objects** (tipos imutáveis com validação):
- `TaskId` / `ProjectId` — wrappers de UUID com validação de formato
- `ModelId` — string no formato `"provider:model"` com validação
- `ThinkingLevel` — enum LOW/MEDIUM/HIGH
- `ExecutionPhase` — enum com mapa de transições válidas + `is_terminal()`
- `SafeFilePath` — path validado dentro do project root

**Entities** (agregados com comportamento):
- `Task` — state machine de status, factory `Task.create()`, `start_pipeline()`, `transition_to()`, `mark_failed/completed/cancelled()`; emite domain events em cada transição
- `Spec` — complexidade (SIMPLE/STANDARD/COMPLEX), fases completadas, conteúdo markdown
- `ImplementationPlan` — phases com subtasks, `get_next_pending_subtask()` respeitando dependências, `mark_subtask_completed()`, `all_subtasks_done()`
- `QAReport` — verdict (APPROVED/REJECTED/UNKNOWN), issues por severidade, `has_recurring_issues()` detecta loop de QA
- `AgentSession` — session com outcome, token usage, steps executados
- `Project` — projeto com config de pipeline (max_parallel_subtasks, max_qa_cycles...)

**Domain Events** (imutáveis, rastreabilidade):
- Task: `TaskCreated`, `TaskStarted`, `TaskCompleted`, `TaskFailed`, `TaskCancelled`, `TaskStatusChanged`
- Agent: `AgentSessionStarted`, `AgentStepCompleted`, `AgentToolCalled`, `AgentSessionCompleted`
- Pipeline: `PhaseTransitioned`, `SubtaskStarted`, `SubtaskCompleted`, `SubtaskFailed`, `QACycleCompleted`

**Ports (ABCs)** — interfaces que a infra deve implementar:
- `AIProviderPort` — `generate_stream()` + `generate()`
- `TaskRepositoryPort`, `ProjectRepositoryPort`, `SpecRepositoryPort`, `PlanRepositoryPort`
- `GitServicePort` — worktree, commit, branch, merge
- `EventBusPort` — publish/subscribe
- `SecurityValidatorPort`
- `IntegrationGatewayPort` — GitHub + Jira

**Domain Services** (lógica sem estado):
- `PhaseStateMachine` — valida transições do `ExecutionPhase`, lança `InvalidPhaseTransitionError`
- `SubtaskDependencyResolver` — topological sort de subtasks (resolve parallelism), detecta ciclos
- `assess_complexity_heuristic()` — avalia SIMPLE/STANDARD/COMPLEX sem LLM (fallback)

### Arquivos

```
src/codeforge/domain/
├── entities/        task.py, spec.py, plan.py, qa_report.py, agent.py, project.py
├── value_objects/   task_id.py, project_id.py, model_id.py, thinking_level.py,
│                    execution_phase.py, file_path.py
├── events/          base.py, task_events.py, agent_events.py, pipeline_events.py
├── ports/           ai_provider.py, task_repository.py, project_repository.py,
│                    spec_repository.py, plan_repository.py, git_service.py,
│                    event_bus.py, security_validator.py, integration_gateway.py
└── services/        phase_state_machine.py, subtask_dependency_resolver.py,
                     complexity_assessor.py
```

### Decisões de design notáveis

- **Dataclasses puras no domain** — sem Pydantic, sem SQLAlchemy. Entidades são classes Python comuns, facilitam testes unitários sem fixtures pesadas.
- **Factory methods com domain events** — `Task.create()` retorna `tuple[Task, list[DomainEvent]]`. Toda mutação retorna os eventos que ela gerou, sem coupling com o EventBus.
- **State machine declarativa** — `VALID_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]]` torna as transições legíveis e testáveis em tabela.
- **`get_next_pending_subtask()` respeita deps** — lê `depends_on` de subtasks e `depends_on` de phases; o coder nunca precisa se preocupar com ordem.

---

## Fase 2 — Tools + Security ✅

**Objetivo:** Sistema de ferramentas que agentes usam para interagir com o filesystem e shell, com camada de segurança robusta.

### O que foi implementado

**Tool Base (`infrastructure/tools/base.py`)**:
- `DefinedTool` ABC — contrato: `name`, `description`, `permission`, `input_schema`, `execute()`
- `BoundTool` — tool + context; `__call__()` aplica automaticamente security hook → write-path containment → truncation
- `ToolPermission` — READ_ONLY (sem hooks), AUTO, REQUIRES_APPROVAL (com hooks)
- `truncate_output()` — 100 KB safety-net, 2.000 linhas máximo

**Tools implementadas** (cada uma em seu próprio arquivo):

| Tool | Permissão | Destaques |
|------|-----------|-----------|
| `ReadTool` | READ_ONLY | Line numbers, offset/limit, sanitiza artefatos de modelo no path, suporte a imagens (base64) |
| `WriteTool` | REQUIRES_APPROVAL | Cria diretórios pai automaticamente, path containment |
| `EditTool` | REQUIRES_APPROVAL | Exige unicidade do `old_string` (salvo `replace_all=True`), retorna erro descritivo |
| `BashTool` | REQUIRES_APPROVAL | Async subprocess, timeout configurável (padrão 120s, máximo 600s), background tasks, truncação inline de 30 KB |
| `GlobTool` | READ_ONLY | `rglob()`, exclui `.git`/`node_modules`/`__pycache__`/`.venv`, cap de 2.000 resultados, ordena por mtime |
| `GrepTool` | READ_ONLY | ripgrep (`rg`) com fallback Python puro; modos `files_with_matches`, `content`, `count`; timeout 60s |

**Security Layer**:

```
Bash command
  → extract_commands()          shlex.split + fallback regex
      → is_command_blocked()    denylist de 30+ comandos
      → validator específico    rm, chmod, git, kill, bash -c, psql, mysql, redis, dropdb
          → PathEscapeError     se path sair do project_dir
```

Validators cobrem:
- `rm /`, `rm -rf ~`, `rm --no-preserve-root`
- `chmod 4755` (setuid)
- `git config user.email` (identidade)
- `kill -1`, `pkill -u root`
- `bash -c 'sudo ...'` (bypass recursivo)
- `psql -c 'DROP TABLE ...'`, `redis-cli FLUSHALL`, `dropdb production_db`

**Agent Config Registry (`infrastructure/config/agent_configs.py`)**:

`AGENT_CONFIGS: dict[AgentType, AgentConfig]` define, para cada tipo de agente:
- `tools: frozenset[str]` — tools permitidas
- `thinking_level: ThinkingLevel`
- `max_steps: int`
- `context_window_warning_pct: float` — 0.85 (injeta aviso)
- `context_window_abort_pct: float` — 0.90 (aborta sessão)
- `convergence_nudge_pct: float | None` — 0.75 para QA/spec_critic (força conclusão)

**Tool Registry (`infrastructure/tools/registry.py`)**:
- `ToolRegistry.register(tool)` / `get(name)` / `registered_names()`
- `get_tools_for_agent(agent_type, context)` — filtra pelo config, faz `bind(context)`, retorna `dict[str, BoundTool]`
- `build_default_registry()` — factory com todos os builtins registrados

### Arquivos

```
src/codeforge/infrastructure/
├── tools/
│   ├── base.py, registry.py
│   ├── bash_tool.py, read_tool.py, write_tool.py
│   ├── edit_tool.py, glob_tool.py, grep_tool.py
└── security/
    ├── denylist.py, command_parser.py, path_containment.py, bash_validator.py
    └── validators/
        ├── filesystem.py, git.py, process.py, shell.py, database.py
```

### Decisões de design notáveis

- **Security hook no BoundTool, não na tool** — O `BashTool` não sabe de segurança; o `BoundTool.__call__()` intercepta antes de chamar `execute()`. Mesma lógica que o Aperant usa com `executeWithHooks`.
- **`shlex.split` como parser principal** — Python já tem isso na stdlib; evita parser caseiro frágil. Fallback regex para edge cases com paths Windows ou quotes malformadas.
- **Grep com fallback Python** — Se `rg` não estiver instalado, GrepTool faz `Path.rglob()` + `re.search()`. Mais lento, mas funcional em qualquer ambiente.
- **Validators retornam `(allowed, reason)`** — Tupla simples, sem exceptions no caminho feliz. Facilita testes e composição.

---

## Fase 3 — AI Provider + Agent Session ✅

**Objetivo:** O coração do sistema — o loop agêntico que alimenta todos os agentes.

### O que foi implementado

**LiteLLM Adapter** (`infrastructure/ai/litellm_provider.py`):
- Implementa `AIProviderPort`
- `generate_stream()` — streaming com LiteLLM, parseia tool calls do stream
- `generate()` — chamada síncrona para reparos de JSON e classificações simples
- Suporte a todos os providers via `"provider/model"` string

**Provider Registry** (`infrastructure/ai/provider_registry.py`):
- Resolve `ModelId("anthropic:claude-sonnet-4")` → provider instance + model string
- Auto-detecção de provider pelo prefixo

**Agent Session Runner** (`application/use_cases/run_agent_session.py`):
```python
async def run_agent_session(config: SessionConfig) -> SessionResult:
    # Loop: modelo gera texto + tool calls
    #       → tools são executadas com ToolContext
    #       → resultado volta como contexto
    # Mecanismos:
    # - Context window: 85% → aviso, 90% → aborta (outcome: context_window)
    # - Convergence nudge: em 75% dos steps para QA agents
    # - Stream inactivity timeout: 60s
    # - Auth retry: 429/401 → tenta trocar provider
    # - Output estruturado: se schema Pydantic definido, parseia resposta final
```

**Session Continuation**:
- Ao atingir 90% do context window, sumariza conversa com LLM leve e abre nova sessão
- Orquestrador não percebe a diferença

---

## Fase 4 — Pipelines de Orquestração ✅

**Objetivo:** Os três pipelines que transformam uma task em código pronto.

### O que foi implementado

**Spec Pipeline** (`application/use_cases/run_spec_pipeline.py`):
- Seleciona sequência de fases por complexidade: 2 (SIMPLE), 4 (STANDARD) ou 7 (COMPLEX)
- Cada fase roda um `run_continuable_session` com prompt específico
- Max 2 retries por fase; se `tool_call_count == 0`, retry com sufixo "MUST use tools"
- Contexto acumulado entre fases (output de cada fase alimenta a próxima via `accumulated_context`)
- Lê `spec.md` ao final e popula `Spec.content`

**Build Pipeline** (`application/use_cases/run_build_pipeline.py`):
- **Planning**: planner agent gera `implementation_plan.json` — se inválido, tenta reparar com `claude-haiku` (LLM barato), re-plana até 3x
- **Coding**: delega para `execute_subtasks`
- **QA Loop**: delega para `run_qa_loop`

**QA Loop** (`application/use_cases/run_qa_loop.py`):
- Até 3 ciclos reviewer → fixer
- `_parse_qa_report()` lê `qa_report.md` e parseia JSON + inferência de verdict por texto
- Detecção de issues recorrentes (mesmo título 3x) → escalação para falha
- Fixer não roda no último ciclo

**Parallel Executor** (`application/use_cases/execute_subtasks.py`):
- Batches de até 3 subtasks simultâneas com `asyncio.create_task` + `asyncio.gather`
- Stagger de 1s entre lançamentos (anti-thundering herd)
- Rate limit: backoff exponencial `min(30s × 2^n, 300s)`, não conta contra retries do subtask
- Outros erros: até 3 retries, depois `mark_stuck()`
- `_get_ready_batch()` usa `set(already_batched)` para não incluir o mesmo subtask duas vezes

**DTOs** (`application/dto/pipeline_dto.py`):
- `SpecPipelineResult`, `QALoopResult`, `SubtaskExecutionResult`, `BuildPipelineResult`

### Arquivos

```
src/codeforge/application/
├── dto/
│   └── pipeline_dto.py
└── use_cases/
    ├── run_spec_pipeline.py
    ├── run_qa_loop.py
    ├── execute_subtasks.py
    └── run_build_pipeline.py
```

### Decisões de design notáveis

- **Fases acumulam contexto** — cada fase recebe o output resumido das anteriores, simulando um desenvolvedor que lembra o que descobriu antes de escrever.
- **Rate limit não conta como retry** — rate limit é um erro de infraestrutura, não de qualidade do subtask. O `attempt_count` é decrementado ao resetar para PENDING.
- **Repair LLM para JSON inválido** — usar `claude-haiku` (modelo barato) para tentar consertar JSON malformado antes de re-planejar evita desperdiçar um context de planner completo.
- **`_parse_qa_report` lê arquivo, não mensagens** — o agente escreve `qa_report.md`, não retorna JSON. Leitura do arquivo é mais robusta que parsear a última mensagem.

---

## Code Review — Fixes aplicados (pós Fases 1–4)

Um code review completo de todas as fases completadas foi realizado. Os seguintes problemas foram encontrados e corrigidos:

### CRITICAL

| # | Problema | Fix |
|---|----------|-----|
| 1 | `ComplexityTier` definido duas vezes (`task.py` e `spec.py`) — tipos incompatíveis em runtime | Extraído para `domain/value_objects/complexity.py`; ambos importam de lá |
| 2 | `mark_failed/completed/cancelled` bypassavam `VALID_TASK_TRANSITIONS`, permitindo transições de estados terminais | Reescritos para usar `transition_to()` internamente; `VALID_TASK_TRANSITIONS` ampliado para incluir `FAILED` em `BACKLOG`/`QUEUED` |
| 3 | `eval`, `exec`, `env`, `xargs` ausentes do denylist (bypass por prefixo ou eval de payload) | Adicionados ao `BLOCKED_COMMANDS` |
| 4 | `SafeFilePath.to_absolute()` retornava path sem resolver symlinks (escape possível via symlink para fora do projeto) | Alterado para retornar `(root / value).resolve()` |

### MAJOR

| # | Problema | Fix |
|---|----------|-----|
| 5 | `truncate_output` podia cortar codepoints UTF-8 no meio ao fatiar por bytes | Lógica de linhas antes de bytes; decode com `errors="ignore"` |
| 6 | `validate_git` não bloqueava `git config --global user.email` (verificação posicional, não via scan) | Reescrito para escanear todos os tokens após `"config"` |
| 7 | `validate_kill` sem `-SIGKILL`, `-SIGTERM`, `-SIGSTOP`, `-SIGHUP` | Adicionados ao conjunto de sinais bloqueados |
| 8 | `GrepTool._python_fallback` sem filtro de `_EXCLUDED_DIRS` (retornava matches de `.git/`, `node_modules/`) | Adicionado filtro equivalente ao `GlobTool` |
| 9 | `validate_psql` não bloqueava `-f`/`--file` (execução de arquivo SQL arbitrário) | Adicionado bloqueio explícito |

### MINOR

| # | Problema | Fix |
|---|----------|-----|
| 10 | `dict` sem type params em `spec.py` | Corrigido para `dict[str, Any]` |
| 11 | `Spec.add_phase` atualizava `updated_at` mesmo quando fase já existia | `updated_at` só atualizado quando fase é realmente nova |

**Novos testes adicionados:** `test_complexity_assessor.py` (7), `test_safe_file_path.py` (9), 13 novos casos em `test_security.py`.

---

## Fase 5B — Domain: Demand, Story, Sprint ✅

**Objetivo:** Implementar as entidades de domínio que refletem a visão de produto completa — o PM layer que dá contexto para toda a execução.

### O que foi implementado

**Value Objects novos:**
- `DemandId`, `StoryId`, `SprintId` — wrappers de UUID seguindo o padrão dos existentes

**Entidades novas:**

- **`Demand`** (Épico) — `DemandStatus` (DRAFT → ACTIVE → BREAKDOWN_PENDING → BREAKDOWN_COMPLETE → IN_SPRINT → DONE), `LinkedProject` (projeto + branch base), métodos `activate()`, `request_breakdown()`, `complete_breakdown(total_tasks)`
- **`Story`** (Entregável) — vinculada a `Demand` e opcionalmente a `Sprint`; `StoryStatus` (BACKLOG → BREAKDOWN_PENDING → BREAKDOWN_COMPLETE → IN_SPRINT → IN_PROGRESS → DONE); método `add_to_sprint(sprint_id)`
- **`Sprint`** — `SprintStatus` (PLANNED → ACTIVE → COMPLETED); `SprintMetrics` com `completion_pct`; `add_story()`/`remove_story()` com idempotência

**Entidades atualizadas:**

- **`Task`** — adicionados `story_id: StoryId | None`, `AssigneeType` (AI/HUMAN/UNASSIGNED), status `CODE_REVIEW` e `AWAITING_REVIEW`, métodos `start_code_review()`, `await_human_review()`, `approve(reviewer)`, `assign_to()`
- **`Project`** — adicionados `repo_url`, `default_branch`, `CodeReviewMode` (AI_ONLY/HUMAN_REQUIRED/HUMAN_OPTIONAL), flags de human-in-the-loop em `ProjectConfig` (`human_review_required`, `auto_start_tasks`, `breakdown_requires_approval`, `auto_merge`)

**Events novos:**
- `demand_events.py` — `DemandCreated`, `DemandBreakdownRequested`, `DemandBreakdownCompleted`, `DemandStatusChanged`
- `story_events.py` — `StoryCreated`, `StoryAddedToSprint`, `StoryStatusChanged`
- `sprint_events.py` — `SprintCreated`, `SprintStarted`, `SprintCompleted`, `SprintStatusChanged`
- `task_events.py` (adicionados) — `TaskCodeReviewStarted`, `TaskAwaitingHumanReview`, `TaskApproved`

**Ports novos:**
- `DemandRepositoryPort`, `StoryRepositoryPort`, `SprintRepositoryPort`

### Pipeline de task completo (com code review)

```
BACKLOG → QUEUED → SPEC_CREATION → PLANNING → CODING → QA_REVIEW → QA_FIXING
  → CODE_REVIEW → [AWAITING_REVIEW] → COMPLETED
```

`AWAITING_REVIEW` só ocorre quando `human_review_required = true`. `CODE_REVIEW` → `COMPLETED` direto quando `code_review_mode = AI_ONLY`.

### Arquivos

```
src/codeforge/domain/
├── entities/        demand.py, story.py, sprint.py
│                    task.py (atualizado), project.py (atualizado)
├── value_objects/   demand_id.py, story_id.py, sprint_id.py
├── events/          demand_events.py, story_events.py, sprint_events.py
│                    task_events.py (atualizado)
└── ports/           demand_repository.py, story_repository.py, sprint_repository.py
```

---

## Fase 5 — Persistence + API ✅

**Objetivo:** Persistir todas as entidades e expor uma API que o CLI e o dashboard possam consumir. Fundação para tudo que vem depois.

### O que foi implementado

**Persistence (`infrastructure/persistence/`)**:
- SQLAlchemy 2.0 async models para `Task`, `Project`, `Demand`, `Story`, `Sprint`, `AgentSession`
- Repositories SQLAlchemy para os ports de domínio: `TaskRepositoryPort`, `ProjectRepositoryPort`, `DemandRepositoryPort`, `StoryRepositoryPort`, `SprintRepositoryPort`
- Repository de `AgentSession` para suporte de API de sessões
- Database bootstrap (`create_engine`, `create_session_factory`, `init_database`)

**Migrations (Alembic):**
- Configuração base (`alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`)
- Migration inicial `0001_phase5_initial_schema.py` cobrindo todas as tabelas da fase

**FastAPI (`api/`)**:
- App factory com DI de repositories (`api/app.py`, `api/dependencies.py`)
- Schemas Pydantic separados em `api/schemas/`
- Routers implementados:
  - `/api/demands`
  - `/api/stories`
  - `/api/sprints`
  - `/api/tasks`
  - `/api/projects`
  - `/api/agents`
- WebSockets:
  - `/ws/tasks/{id}/progress`
  - `/ws/agents/{session_id}/logs`

### Testes adicionados
- `tests/integration/infrastructure/test_sqlalchemy_repositories.py` (6 testes)
- `tests/integration/api/test_routes.py` (3 testes)
- Cobertura de roundtrip de persistence com SQLite e rotas FastAPI com `httpx.AsyncClient`

### Resultado
- Suite completa: **267 passed, 0 failed**

---

## Fase 5C — Agent Intelligence Layer ✅

**Objetivo:** Tornar o motor de agente mais robusto em produção e adicionar inteligência persistida por projeto — skills e memória que os agentes carregam no contexto. Fundação para os agentes de PM da Fase 7 (breakdown, demand_assistant) que precisam de contexto rico e estável entre execuções.

**Motivação:** Análise comparativa com o projeto nanobot revelou três problemas concretos no motor atual e dois recursos ausentes que têm alto impacto no resultado dos agentes analíticos.

### Melhorias no motor

**1. Tolerância a JSON malformado (`litellm_provider.py`)**

LLMs ocasionalmente geram tool call arguments com JSON truncado ou malformado (especialmente com streaming). Antes, `json.JSONDecodeError` silenciosamente descartava os argumentos (`tool_input = {}`). Agora, tenta recuperar via `json_repair` antes de desistir:

```python
# antes
except json.JSONDecodeError:
    tool_input = {}

# depois
except json.JSONDecodeError:
    try:
        from json_repair import repair_json
        tool_input = json.loads(repair_json(tc_data["arguments"]))
    except Exception:
        tool_input = {}
```

Dependência adicionada ao `pyproject.toml`: `json-repair>=0.30`.

**2. Tool error hint auto-correção (`run_agent_session.py`)**

Quando uma tool lança exceção, o erro era devolvido puro ao LLM. Sem instrução explícita, modelos tendem a repetir a mesma chamada inválida em loop. Adicionado hint:

```
[Tool Error]: <mensagem original>

[Analyze the error above and try a different approach.]
```

**3. Separação de runtime context no `PromptBuilder`**

Informações efêmeras (ex: descrição da tarefa atual, output de sessão anterior) permanecem em mensagens do usuário. Skills e memória do projeto — que raramente mudam — ficam no system prompt. Isso preserva o cache de prompt do Anthropic entre turns, reduzindo custo e latência.

`build_system_prompt()` agora aceita `skills: list[str]` e `memory_entries: list[str]`. A estrutura do prompt resultante:

```
[instrução base do agente]
[Working directory: ...]

## Project Memory
[entradas de memória do projeto]

## Project Instructions
[skills ativas para este agente]

## Additional Context
[contexto extra passado pelo orquestrador]
```

### Novas entidades de domínio

**`AgentSkill`** — bloco de instrução nomeado, escopo opcional por projeto e/ou tipo de agente. Quando `always_active=True`, injetado no system prompt de cada sessão do agente. Permite personalizar o comportamento dos agentes por projeto sem alterar código.

Exemplos de uso:
- `name="code_style"`, `agent_type=CODER`: "Neste projeto sempre use Tailwind, nunca CSS modules"
- `name="review_focus"`, `agent_type=QA_REVIEWER`: "Priorize cobertura de casos de erro sobre style"
- `name="stack_context"`, `agent_type=None` (global): descreve a stack para todos os agentes

**`AgentMemory`** — bloco de texto chaveado por `(project_id, key)`, representando conhecimento condensado acumulado sobre o projeto. Atualizado manualmente (via API) ou programaticamente por agentes analíticos em fases futuras.

Exemplos de uso:
- `key="conventions"`: padrões identificados pelo breakdown agent ao ler o codebase
- `key="qa_patterns"`: problemas recorrentes que o QA encontrou nas últimas execuções
- `key="architecture"`: resumo da arquitetura gerado pelo demand_assistant

### Novos ports de domínio

- `AgentSkillRepositoryPort` — `save`, `get`, `list_for_agent(project_id, agent_type, only_active)`, `delete`
- `AgentMemoryRepositoryPort` — `save`, `get(project_id, key)`, `list_for_project`, `delete`

`list_for_agent` resolve a hierarquia: skills globais (project_id=None) + skills do projeto + skills do agent_type específico + skills genéricas (agent_type=None).

### Persistence

**Tabela `agent_skills`:**

| Coluna | Tipo | Notas |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID |
| name | VARCHAR(255) | |
| content | TEXT | instruções em markdown |
| always_active | BOOLEAN | se true, sempre injetada no system prompt |
| project_id | VARCHAR(36) FK nullable | NULL = skill global |
| agent_type | VARCHAR(64) nullable | NULL = para todos os agentes |
| created_at / updated_at | DATETIME | |

**Tabela `agent_memory`:**

| Coluna | Tipo | Notas |
|--------|------|-------|
| id | VARCHAR(36) PK | UUID |
| project_id | VARCHAR(36) FK | CASCADE |
| key | VARCHAR(255) | |
| content | TEXT | markdown |
| updated_at | DATETIME | |
| — | UNIQUE(project_id, key) | uma entrada por chave por projeto |

Migration: `0002_agent_intelligence.py`

### API

Novos endpoints em `/api/projects/{project_id}/`:

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/skills` | Lista skills do projeto (inclui globais) |
| POST | `/skills` | Cria nova skill |
| PUT | `/skills/{skill_id}` | Atualiza nome, conteúdo ou always_active |
| DELETE | `/skills/{skill_id}` | Remove skill |
| GET | `/memory` | Lista todas as entradas de memória do projeto |
| PUT | `/memory` | Upsert por key (cria ou atualiza) |
| DELETE | `/memory/{key}` | Remove entrada por key |

### Arquivos

```
src/codeforge/domain/
├── entities/        agent_skill.py, agent_memory.py
└── ports/           agent_skill_repository.py, agent_memory_repository.py

src/codeforge/infrastructure/
├── persistence/
│   ├── models.py         (+ AgentSkillModel, AgentMemoryModel)
│   └── repositories.py   (+ SqlAlchemyAgentSkillRepository, SqlAlchemyAgentMemoryRepository)

alembic/versions/
└── 0002_agent_intelligence.py

src/codeforge/application/services/
└── prompt_builder.py     (+ skills, memory_entries params)

src/codeforge/infrastructure/ai/
└── litellm_provider.py   (json_repair fallback)

src/codeforge/application/use_cases/
└── run_agent_session.py  (tool error hint)

src/codeforge/api/
├── schemas/intelligence.py
├── routers/intelligence.py
├── dependencies.py  (+ AgentSkillRepository, AgentMemoryRepository no container)
└── app.py           (+ intelligence router)
```

### Testes adicionados (29)

```
tests/unit/domain/
  test_agent_skill.py          6
  test_agent_memory.py         5

tests/unit/infrastructure/
  test_motor_robustness.py     8   (json_repair + tool error hint)

tests/unit/application/
  test_prompt_builder_v2.py    5   (skills + memory injection)

tests/integration/infrastructure/
  test_agent_intelligence_repositories.py   5

Total novo: 29 — Suite: 296 passed, 0 failed
```

---

## Fase 6 — CLI + Execução via Claude Code ✅

**Objetivo:** Primeiro ponto de contato real com o produto. Valida a hipótese central: task bem descrita → Claude Code → PR + code review.

Esta fase é o equivalente ao "Phase 0" de validação de produto — o menor fluxo que prova que o núcleo funciona antes de construir PM layer, dashboard, etc.

### O que foi implementado

**Git Service (`infrastructure/git/git_service.py`)**

Implementa `GitServicePort` usando `asyncio.create_subprocess_exec` com `git -C <path>`:

- `create_worktree(repo_path, task_id)` → branch `codeforge/task-{id}` + worktree em `.codeforge/worktrees/task-{id}/`; retorna `WorktreeInfo(path, branch)`
- `remove_worktree(worktree_path)` — remove worktree e deleta a branch criada
- `commit(repo_path, message)` → retorna hash do commit (`git rev-parse HEAD`)
- `get_diff(repo_path, base_branch)` / `get_changed_files(repo_path, base_branch)` — comparação contra branch base
- `get_current_branch(repo_path)`, `create_branch(repo_path, name)`, `merge(repo_path, branch)`
- Helper `_run_git(repo_path, *args)` — lança `RuntimeError` em saída não-zero

**Executor via Claude Code (`infrastructure/execution/claude_code_executor.py`)**

```python
@dataclass
class ExecutionConfig:
    executor: str          # "claude" | "opencode" | "aider"
    task_prompt: str
    worktree_path: str
    timeout_seconds: int = 600

@dataclass
class ExecutionResult:
    success: bool
    exit_code: int
    output: str
    changed_files: list[str]
    diff: str
```

- `ClaudeCodeExecutor.execute()` — spawna subprocess dentro do worktree com streaming de stdout/stderr; mata o processo em timeout
- `build_task_prompt(title, description, acceptance_criteria, worktree_path)` — usa `GlobTool` + `ReadTool` para coletar até 6 arquivos Python do repo como contexto; monta prompt estruturado com título, descrição, acceptance criteria e snippets reais do codebase
- `_collect_git_changes()` — verifica se há uncommitted changes rastreadas (ignora `??` untracked) ou cai para `HEAD~1..HEAD` (captura commits feitos pelo executor)
- `_build_command()` — mapeia `executor` para o comando correto: `claude -p --dangerously-skip-permissions`, `opencode run`, `aider --message`

**Code Review interno (`application/use_cases/run_code_review.py`)**

Usa o motor agêntico interno (Fases 1–4) — não spawna Claude Code:

```python
@dataclass
class CodeReviewInput:
    task_title: str
    task_description: str
    acceptance_criteria: list[str]
    diff: str
    changed_files: list[str]

@dataclass
class CodeReviewReport:
    verdict: str           # "approved" | "changes_requested"
    summary: str
    issues: list[CodeReviewIssue]
```

- Cria sessão de agente `QA_REVIEWER` com `output_schema=_ReviewSchema` (Pydantic)
- Parseia JSON da resposta; fallback para `verdict=changes_requested` com issue "Code review inconclusive" quando o modelo retorna texto não estruturado

**CLI (`cli/main.py`, `cli/config.py`, `cli/output.py`)**

Estrutura `_Runtime` centraliza engine + session_factory + 4 repositories. `_run_async[T]()` (PEP 695) faz bridge entre comandos Typer síncronos e código async.

```bash
codeforge project init <path>          # cria .codeforge/config.toml + .codeforge/codeforge.db
codeforge project status               # lista projetos no banco local

codeforge task create <title>          # --description "..." ou --file path.md
codeforge task list                    # --status BACKLOG|CODING|... (opcional)
codeforge task run <id>                # cria worktree → spawna executor → salva execução
codeforge task review <id>             # code review do diff salvo
codeforge task status <id>             # mostra branch, worktree, diff_chars, review verdict

codeforge config set model <model>     # ex: anthropic:claude-sonnet-4-6
codeforge config set executor <exec>   # claude | opencode | aider
codeforge config set execution_timeout <secs>
codeforge config set default_branch <branch>
```

`task run` oferece prompt interativo "Rodar code review automático agora?" quando stdout é TTY. Aceita `--review / --no-review` para uso em scripts.

**Persistence para execuções e reviews (`infrastructure/persistence/`)**

Tabelas adicionadas na Fase 6:

| Tabela | Conteúdo |
|--------|----------|
| `task_executions` | exit_code, output, changed_files (JSON), diff, created_at |
| `task_reviews` | verdict, summary, issues (JSON), created_at |

Repositories: `SqlAlchemyTaskExecutionRepository`, `SqlAlchemyTaskReviewRepository`.

**Configuração local (`.codeforge/config.toml`)**

```toml
[project]
name = "my-project"
default_branch = "main"

[agent]
model = "anthropic:claude-sonnet-4-6"
executor = "claude"
execution_timeout = 600

[database]
url = "sqlite+aiosqlite:///path/to/.codeforge/codeforge.db"
```

Carregado com `tomllib` (stdlib Python 3.11+); salvo com `toml`. `find_project_root()` sobe o filesystem até encontrar `.codeforge/config.toml`.

**Saída Rich (`cli/output.py`)**

- `render_projects()` / `render_tasks()` — tabelas Rich com ID truncado (8 chars), status, assignee
- `render_diff_summary()` — painel de arquivos alterados + preview do diff (3.000 chars)
- `render_review()` — painel com verdict/summary + tabela de issues por severidade

### Autenticação

O `task run` usa o `claude` CLI, que autentica via OAuth do claude.ai (login via browser, configurado pelo próprio CLI em `~/.claude/.credentials.json`). **Não precisa de `ANTHROPIC_API_KEY`.**

O `task review` usa LiteLLM diretamente (motor interno das Fases 1–4). **Precisa de `ANTHROPIC_API_KEY` no ambiente:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Fluxo completo

```
codeforge task run <id>
  → GitService.create_worktree()          branch: codeforge/task-{id}
  → build_task_prompt()                   lê até 6 .py do worktree para contexto
  → ClaudeCodeExecutor.execute()          spawna: claude -p --dangerously-skip-permissions "<prompt>"
      → stdout/stderr streaming
      → timeout em 600s
  → _collect_git_changes()                diff do que o executor commitou (ignora untracked)
  → SqlAlchemyTaskExecutionRepository     persiste resultado
  → [interativo] → task review <id>
      → run_code_review()                 QA_REVIEWER agent via LiteLLM com o diff
      → SqlAlchemyTaskReviewRepository    persiste report
```

### Arquivos

```
src/codeforge/
├── infrastructure/
│   ├── git/
│   │   └── git_service.py
│   ├── execution/
│   │   └── claude_code_executor.py
│   └── persistence/
│       ├── models.py         (+ TaskExecutionModel, TaskReviewModel)
│       └── repositories.py   (+ SqlAlchemyTaskExecutionRepository, SqlAlchemyTaskReviewRepository)
│
├── application/
│   └── use_cases/
│       └── run_code_review.py
│
└── cli/
    ├── main.py
    ├── config.py
    └── output.py
```

### Bugs encontrados em teste real (pós-implementação)

Dois bugs descobertos ao rodar o fluxo completo end-to-end, não cobertos pelos testes unitários mockados:

| # | Bug | Causa raiz | Fix |
|---|-----|-----------|-----|
| 1 | `task run` concluía com exit 0 mas sem criar nenhum arquivo | `claude -p` sem `--dangerously-skip-permissions` exibia prompt de aprovação de escrita; sem TTY, o processo saía silenciosamente | Adicionado `--dangerously-skip-permissions` ao comando |
| 2 | Diff e arquivos alterados sempre vazios mesmo após executor commitar | `git status --porcelain` retornava `?? __pycache__/` (untracked), que é truthy; o código entrava no branch "uncommitted changes" e chamava `git diff --name-only` que devolvia vazio (mudanças já commitadas) | Filtrar linhas `??` antes de checar se há mudanças rastreadas |

### Testes adicionados (11)

```
tests/unit/infrastructure/
  test_git_service.py              4   (worktree, commit, changed_files, remove)
  test_claude_code_executor.py     2   (execute + output/diff, build_task_prompt)

tests/unit/application/
  test_run_code_review.py          2   (structured output, fallback unstructured)

tests/integration/
  test_cli_commands.py             3   (help, project init, task create+list)

Total novo: 11 — Suite: 307 passed, 0 failed
```

### O que esta fase valida

1. Claude Code consegue executar tasks com contexto de repo real?
2. Qual nível de detalhe no prompt é necessário para execução confiável?
3. O code review automático identifica problemas reais no diff?
4. Em quantas tasks o resultado é "aceito sem retrabalho"?

Sem respostas satisfatórias aqui, as fases seguintes de PM layer e dashboard não valem o esforço.

---

## Fase 7 — Agentes de PM + Breakdown + Integrações ✅

**Objetivo:** Entregar os agentes de PM e integração GitHub que conectam o fluxo de execução da task ao fluxo real de entrega (breakdown útil + PR aberto).

### O que foi implementado

**1) Breakdown Agent (prioridade máxima)**

- Novos `AgentType`: `BREAKDOWN` e `DEMAND_ASSISTANT`
- Novos system prompts em `application/services/prompt_builder.py` para ambos os agentes
- Novas configs em `infrastructure/config/agent_configs.py`:
  - `BREAKDOWN` com tools somente leitura (`Read`, `Glob`, `Grep`)
  - `DEMAND_ASSISTANT` sem tools de filesystem
- Novo use case `run_breakdown` (`application/use_cases/run_breakdown.py`):
  - Recebe `BreakdownInput` (story + repo path + project)
  - Roda `run_agent_session` com output estruturado (`tasks[]`)
  - Faz fallback para `success=False` quando o modelo não retorna JSON estruturado
  - Persiste tasks no `TaskRepositoryPort` com `story_id` vinculado
- CLI: `codeforge breakdown run <story_id> --repo <path>`
- API: `POST /api/stories/{story_id}/breakdown`

**2) GitHub Gateway + PR flow**

- Novo port: `domain/ports/github_gateway.py` (`GitHubGatewayPort`)
- Novo adapter: `infrastructure/integrations/github_gateway.py` usando `httpx.AsyncClient` + GitHub REST API v3 + `GITHUB_TOKEN`
- Novo use case `push_task_to_github`:
  - Faz push da branch do worktree (`git push -u origin <branch>`)
  - Cria PR no GitHub com título derivado da task
  - Body inclui descrição, acceptance criteria e link de diff (`compare` URL)
  - Persiste `pr_url` na task
- Entidade `Task` atualizada com `pr_url: str | None`
- Persistence atualizada (`TaskModel`, repository mapper) + migration `0003_task_pr_url.py`
- CLI: `codeforge task push <id>`
- API: `POST /api/tasks/{id}/push`

**3) Demand Assistant (prioridade menor)**

- Novo use case `run_demand_assistant` (`application/use_cases/run_demand_assistant.py`):
  - Estrutura texto livre em objetivo de negócio + critérios + stories
  - Retorna entidades de domínio (`Demand`, `Story[]`)
  - Persiste quando `persist=True`
  - Fallback estruturado para `success=False` quando output é inválido
- CLI: `codeforge demand create "descrição livre"`
  - Mostra resultado estruturado
  - Pergunta `Salvar? [y/N]`
  - Persiste demanda/stories apenas quando confirmado
- API: `POST /api/demands/assist`

### Arquivos principais

```
src/codeforge/domain/
├── entities/agent.py                    (+ BREAKDOWN, DEMAND_ASSISTANT)
├── entities/task.py                     (+ pr_url)
└── ports/github_gateway.py              (novo)

src/codeforge/application/use_cases/
├── run_breakdown.py                     (novo)
├── run_demand_assistant.py              (novo)
└── push_task_to_github.py               (novo)

src/codeforge/infrastructure/
├── config/agent_configs.py              (+ novos AgentConfigs)
├── integrations/github_gateway.py       (novo)
├── git/git_service.py                   (+ push_branch/get_remote_url)
└── persistence/
    ├── models.py                        (+ tasks.pr_url)
    └── repositories.py                  (+ map pr_url)

src/codeforge/api/
├── routers/stories.py                   (+ /api/stories/{id}/breakdown)
├── routers/tasks.py                     (+ /api/tasks/{id}/push)
├── routers/demands.py                   (+ /api/demands/assist)
└── schemas/
    ├── task.py                          (+ TaskPushResponseSchema, pr_url)
    ├── story.py                         (+ StoryBreakdownRunSchema)
    └── demand.py                        (+ Demand assist schemas)

src/codeforge/cli/main.py
├── task push
├── breakdown run
└── demand create

alembic/versions/
└── 0003_task_pr_url.py                  (novo)
```

### Avaliação de qualidade pós-entrega

Avaliação realizada após implementação da fase. Problemas encontrados e corrigidos:

| Prioridade | Local | Problema | Fix aplicado |
|------------|-------|----------|--------------|
| HIGH | `tasks.py` transition | `ValueError` da máquina de estados resultava em HTTP 500 | `try/except ValueError` → 422 com detalhe |
| HIGH | `tasks.py` list | `TaskStatus(bad_value)` resultava em HTTP 500 | Idem |
| HIGH | `stories.py` list | `StoryStatus(bad_value)` resultava em HTTP 500 | Idem |
| HIGH | `demands.py` list | `DemandStatus(bad_value)` resultava em HTTP 500 | Idem |
| MEDIUM | `run_breakdown.py` | `assert isinstance` removível com `python -O` | Substituído por `if not isinstance(...): return` |
| MEDIUM | `run_demand_assistant.py` | Idem | Idem |
| MEDIUM | `stories.py` breakdown | Falha do agente retornava HTTP 200 + lista vazia | Retorna 422 com detalhe do raw_output |
| MEDIUM | `stories.py` | `_task_to_response` duplicado em relação a `tasks.py` | Renomeado para `task_to_response` (público) e importado |
| LOW | Todos routers | `HTTP_422_UNPROCESSABLE_ENTITY` (deprecated) | Substituído por `HTTP_422_UNPROCESSABLE_CONTENT` |

### Testes adicionados (10)

```
tests/unit/application/
  test_run_breakdown.py          2
  test_run_demand_assistant.py   2
  test_push_task_to_github.py    1

tests/unit/infrastructure/
  test_github_gateway.py         2

tests/integration/api/
  test_routes.py                 3  (+ invalid status → 422, state machine → 422, bad filter → 422)

Total novo: 10 — Suite: 317 passed, 0 failed
```

---

## Fase 8 — Dashboard React (Completa)

**Objetivo:** Interface visual para PM e dev. O PM vê o produto, o dev vê o pipeline. Cada um no seu nível de detalhe.

React 19 + TypeScript + Tailwind CSS 4 + Zustand + TanStack Query

### Status do Desenvolvimento (Entregável Mínimo)
✅ **Step 1:** Sidebar + Roteamento base configurado com Zustand.
✅ **Step 2:** ProductView (Demandas e Histórias) listando dados reais da API.
✅ **Step 3:** Modal "Nova Demanda com IA" funcional com endpoint `/api/demands/assist`.
✅ **Step 4:** KanbanView (Sprint Board) funcional dividindo tasks por colunas mapeadas ao status.
✅ **Step 5:** TaskDetailPanel (slide-in) exibindo badge de assign e tabs de Pipeline/Logs.
✅ **Step 6:** AgentMonitorView com polling real de `/api/agents` a cada 5s e métricas locais.
✅ **Step 7:** SettingsView com leitura real de `GET /api/projects/{id}` e renderizacao das politicas/configs do projeto.
✅ **Step 8:** Base de gestão manual/Jira-like entregue: criação manual de Story por demanda, criação manual de Task no board e planejamento de Sprint com seleção de histórias e ações de iniciar/concluir.

### Fluxos manuais adicionados após o MVP inicial
- **Criação manual de Story:** modal em `DemandCard`, persiste via `POST /api/stories` e atualiza a árvore da demanda.
- **Criação manual de Task:** modal no `KanbanView`, permite criar task manual no backlog vinculando opcionalmente a uma Story.
- **Planejamento de Sprint:** modal de Sprint com criação via `POST /api/sprints`, vinculação de histórias via `POST /api/stories/{id}/add-to-sprint` e ações de início/conclusão.
- **Hierarquia visível na UI:** a ProductView agora explicita `Demanda -> Story -> Task`, mostrando lado a lado trabalho manual e breakdown por IA.

### Ajustes complementares aplicados durante a implementação
- `GET /api/agents` passou a aceitar listagem global sem exigir `task_id`, mantendo filtro opcional por task.
- Sidebar agora exibe seletor de projeto ativo, alinhando a navegação com o fluxo PM/Dev.
- Melhorado o tratamento de erro do client HTTP no frontend para exibir `detail` da API quando disponível.
- Settings passou a refletir os dados reais do backend; integracoes seguem como placeholder visual porque a API ainda nao expoe estado seguro de secrets.
- ProductView passou a mostrar a hierarquia Demanda -> Story -> Task, deixando visivel o trabalho humano/manual junto do breakdown por IA.
- Adicionadas criacao manual de Story por demanda, criacao manual de Task no backlog e modal de planejamento de Sprint com selecao de historias e acoes de iniciar/concluir sprint.
- Corrigido o backend de agentes para suportar monitoramento global do motor sem depender de `task_id`, necessario para a tela operacional.

### Avaliação pós-entrega e correções aplicadas

| # | Severidade | Problema | Arquivo | Status |
|---|------------|----------|---------|--------|
| 1 | CRITICAL | `NewDemandModal` chamava `POST /api/demands` após `/assist`, criando demanda duplicada | `NewDemandModal.tsx` | ✅ Corrigido |
| 2 | CRITICAL | `BreakdownModal` usava checkboxes `defaultChecked` sem estado — "Aprovar Selecionadas" aprovava tudo independente da seleção | `BreakdownModal.tsx` | ✅ Corrigido |
| 3 | CRITICAL | Race condition: `assignMutation.mutate('ai')` e `transitionMutation.mutate('coding')` disparados em paralelo | `TaskDetailPanel.tsx` | ✅ Corrigido (chain com `mutateAsync`) |
| 4 | HIGH | Tasks `completed`/`failed` invisíveis — nenhuma coluna no Kanban as exibia | `KanbanView.tsx` | ✅ Corrigido (coluna DONE adicionada) |
| 5 | HIGH | Botão "Interromper Agente" sem handler — clique silencioso | `TaskDetailPanel.tsx` | ✅ Corrigido (disabled) |
| 6 | HIGH | Botão "Aprovar & Merge" sem handler — PR nunca criado | `TaskDetailPanel.tsx` | ✅ Corrigido (chama `pushTask`) |
| 7 | HIGH | Select "Responsável" decorativo sem lógica de filtro | `KanbanView.tsx` | ✅ Corrigido (filtra `assignee_type`) |
| 8 | HIGH | `ProductView` duplicava `GlobalProjectLoader` (useEffect + useQuery de projetos) | `ProductView.tsx` | ✅ Corrigido (removida duplicata) |
| 9 | HIGH | "Memória do Projeto" com id `'settings'` causava highlight duplo com "Configurações" | `Sidebar.tsx` | ✅ Corrigido (`!disabled` na condição de destaque) |
| 10 | MEDIUM | `PipelineTab` exibia apenas 4 das 7 fases reais do pipeline de agentes | `PipelineTab.tsx` | ✅ Corrigido (todas 7 fases: complexity_assessor, spec_writer, spec_critic, planner, coder, qa_reviewer, qa_fixer) |
| 11 | MEDIUM | `AgentTable` calculava progresso com `steps_executed * 8` — estimativa incorreta | `AgentTable.tsx` | ✅ Corrigido (usa `task.execution_progress.progress_pct`) |
| 12 | LOW | `createDemand` e `assistDemand` tipadas como `any` | `api/demands.ts` | ✅ Corrigido (interfaces `CreateDemandInput` e `AssistDemandResult`) |
| 13 | LOW | `breakdownStory` tipada como `any` | `api/stories.ts` | ✅ Corrigido (retorna `Task[]`) |

**Build final:** `tsc -b && vite build` — 0 erros TypeScript, 0 warnings.

### Visão do PM — por entregável

```
Demanda: "Checkout com PIX"
  Entregável: Pagamento via PIX                    ██████░░░░  60%
    [DONE]         backend-api: endpoint POST /payments/pix
    [CODE REVIEW]  frontend-web: componente QRCodeDisplay
    [CODING]       backend-api: integração com API do banco
    [BACKLOG]      frontend-web: polling de status
```

- Criar/editar demandas e entregáveis com assistência de IA
- Disparar breakdown e aprovar tasks geradas
- Sprint planning: arrastar entregáveis para sprint
- Progresso em tempo real via WebSocket

### Visão do Dev — kanban clássico

```
BACKLOG | SPEC | PLANNING | CODING | QA | CODE REVIEW | DONE
```

- Filtros por demanda / entregável / responsável (humano ou IA) / repositório
- Card da task: descrição, assignee, branch, link do PR
- Atribuir task para IA (spawna Claude Code) ou pegar manual

### Task detail

Tabs por task:
- **Pipeline** — visual do progresso: qual etapa, tempo gasto, subtasks
- **Spec** — spec.md renderizado (quando gerado pelo agente interno)
- **Diff** — alterações de código com syntax highlight
- **Code Review** — report completo com issues e verdict
- **Logs** — output em tempo real do Claude Code (via WebSocket)

### Human-in-the-loop UI

- Notificação: "IA concluiu, aguardando aprovação do breakdown"
- Modal de aprovação: lista de tasks com edição inline antes de aprovar
- Code review: diff + issues do agente, botões Aprovar / Pedir ajustes

---

## Fase 9 — Time e Colaboração (PENDENTE)

**Objetivo:** Múltiplos usuários, papéis (PM / Dev), notificações, audit trail.

- Autenticação (início: API key simples; depois: OAuth com GitHub)
- Papéis: PM cria demandas e aprova; Dev pega tasks e faz review
- Notificações: tarefa concluída, PR pronto para review, breakdown aguardando aprovação
  - Channels: email, Slack webhook, in-app
- Comentários em tasks e em code review
- Audit trail de eventos de domínio (quem fez o quê, quando)
- Métricas de sprint: tasks done/total, lead time médio, taxa de sucesso da IA

---

## Fase 10 — Cloud Execution (PENDENTE)

**Objetivo:** Eliminar a necessidade de ter o Claude Code instalado na máquina local. Cada execução roda em uma VM efêmera na nuvem, isolada e descartável.

### Modelo de execução

```
Task atribuída para IA
  → CodeForge provisiona VM (pod Linux)
      → VM sobe com: Claude Code instalado + credenciais injetadas
          → Clona o repositório na branch base
              → Claude Code executa a task
                  → Commita, cria PR
                      → VM é destruída
                          → CodeForge captura resultado (PR, diff, status)
```

### Infraestrutura

- Kubernetes Jobs ou Fly.io Machines ou Modal para provisionamento de pods
- Credential injection seguro: GitHub token, NPM token, etc. via secrets — nunca em variáveis de ambiente expostas
- Cada task roda em pod isolado → múltiplas tasks em paralelo sem interferência
- Timeout por task: VM é destruída mesmo se Claude Code travar
- Logs em tempo real do pod para o dashboard via WebSocket

### Modelo de negócio

- Free: execução local (usuário tem Claude Code na máquina)
- Paid: execução em cloud (minutos de VM por mês, ou por tarefa executada)
- Enterprise: cloud privado (deploy na infraestrutura do cliente)

### Considerações de segurança

- Repositório é clonado fresh a cada execução — sem estado compartilhado entre tasks
- Credenciais nunca persistem na VM após destruição
- Opção de execução na infraestrutura do cliente (on-premise) para código que não pode sair da empresa
