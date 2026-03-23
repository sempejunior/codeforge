# CodeForge — Visão de Produto

## O problema

Desenvolvedores passam uma fração enorme do tempo em trabalho repetitivo e previsível: implementar features já especificadas, escrever boilerplate, corrigir bugs simples, ajustar código conforme feedback de PR. Trabalho que exige atenção, mas não criatividade.

Ferramentas de AI coding existentes (Copilot, Cursor, Claude Code) ajudam _durante_ a escrita — mas o desenvolvedor ainda precisa estar presente o tempo todo, dirigindo cada passo. O modelo mental ainda é "assistente de autocomplete", não "colega autônomo".

## A solução

CodeForge é uma plataforma de AI coding autônoma. O desenvolvedor descreve o que quer (ou importa do GitHub/Jira), e o sistema executa o ciclo completo:

```
Tarefa criada
  → Avaliação de complexidade
    → Especificação técnica (com pesquisa)
      → Plano de implementação (phases + subtasks)
        → Implementação (pode paralelizar subtasks)
          → QA automatizado (testes + revisão de código)
            → Correção de problemas (loop até 3x)
              → Pull Request pronto para review humano
```

Tudo acontece em **git worktrees isolados** — a branch principal nunca é tocada. O desenvolvedor só entra no final para revisar e fazer merge.

## Diferencial

| Característica | Copilot / Cursor | Claude Code | CodeForge |
|---------------|-----------------|-------------|-----------|
| Requer desenvolvedor presente | Sim | Sim | Não |
| Planeja antes de implementar | Não | Parcial | Sim |
| QA automatizado com loop de correção | Não | Não | Sim |
| Isolamento por git worktree | Não | Não | Sim |
| Integração com Jira/GitHub Issues | Não | Não | Sim |
| Dashboard de acompanhamento | Não | Não | Sim |
| Multi-provider (OpenAI, Anthropic, Gemini...) | Parcial | Parcial | Sim (LiteLLM) |

## Interfaces

### CLI — para desenvolvedores

Interface principal. Roda pipelines, gerencia projetos e tasks, exibe progresso em tempo real.

```bash
# Criar e executar uma task
codeforge task create "Adicionar autenticação JWT"
codeforge task run 1

# Importar do Jira ou GitHub
codeforge task create --from-jira PROJ-123
codeforge task create --from-github owner/repo#42

# Acompanhar progresso
codeforge task status 1

# Ver logs do agente em tempo real
codeforge agent logs 1
```

### Dashboard React — para acompanhamento visual

Interface web (localhost:8000) com:
- **Kanban board** — tasks em colunas por status (Backlog → Spec → Planning → Coding → QA → Done)
- **Task detail** — spec, plano de implementação, QA report, logs do agente em real-time
- **Agent monitor** — sessões ativas, token usage, tool calls por passo
- **Settings** — API keys, modelos, preferências de pipeline

---

## Fluxo técnico detalhado

### Pipeline Spec (avalia e especifica a tarefa)

```
Complexidade SIMPLE   → quick_spec → validação                         (2 fases)
Complexidade STANDARD → discovery → requirements → spec → validação    (4 fases)
Complexidade COMPLEX  → discovery → requirements → research → context
                       → spec → critique → validação                   (7 fases)
```

Cada fase é uma sessão de agente que produz um arquivo de output. O output de cada fase alimenta a próxima (acumulação de contexto). Falhas têm até 2 retries automáticos.

### Pipeline Build (implementa a tarefa)

```
1. PLANNING
   Agente 'planner' lê spec + codebase → gera implementation_plan.json
   Se JSON inválido: tenta reparar com LLM barato → se ainda inválido: re-plan (até 3x)

2. CODING
   Loop de subtasks (respeitando dependências declaradas no plano):
   - Agente 'coder' implementa um subtask por vez
   - Commita após cada subtask completado
   - Subtasks podem rodar em paralelo (até 3 simultâneos)
   - Rate limit → pausa + resume automático (backoff exponencial)
   - Após 3 falhas no mesmo subtask → marca como 'stuck', avança para o próximo

3. QA (até 3 ciclos)
   Agente 'qa_reviewer' roda testes, valida código, escreve verdict
   → Se APPROVED: pipeline completo, cria PR
   → Se REJECTED: agente 'qa_fixer' corrige problemas → volta ao reviewer
   → Issues recorrentes (mesmo título 3x): escalação para falha
```

### Isolamento por git worktree

Cada task recebe seu próprio git worktree em `.codeforge/worktrees/task-{id}/`. Agentes trabalham **exclusivamente** dentro do worktree — path containment garante que nenhuma tool escreve fora do escopo. Ao final, um PR é criado ou o worktree é limpo.

---

## Agentes e seus papéis

| Agente | Thinking | Max Steps | Propósito |
|--------|----------|-----------|-----------|
| `complexity_assessor` | medium | 50 | Avalia se a task é SIMPLE/STANDARD/COMPLEX |
| `spec_writer` | high | 150 | Escreve spec.md a partir dos requirements |
| `spec_critic` | high | 100 | Revisa e corrige a spec |
| `planner` | high | 200 | Cria implementation_plan.json com phases e subtasks |
| `coder` | medium | 1000 | Implementa subtasks, commita após cada um |
| `qa_reviewer` | high | 300 | Roda testes, valida código, escreve qa_report |
| `qa_fixer` | medium | 400 | Corrige issues do QA report |

---

## Providers suportados (via LiteLLM)

Qualquer provider compatível com LiteLLM: Anthropic, OpenAI, Google Gemini, AWS Bedrock, Azure, Mistral, Groq, Ollama (local), OpenRouter e outros.

Configuração no `~/.codeforge/config.toml`:

```toml
[default]
model = "anthropic:claude-sonnet-4-20250514"

[providers.anthropic]
api_key = "sk-ant-..."

[providers.ollama]
base_url = "http://localhost:11434"
```

---

## Roadmap de features

### Curto prazo (Phases 3–5)
- [ ] Agent Session loop com LiteLLM (streaming, tool calls, context window management)
- [ ] Pipelines Spec e Build completos
- [ ] Persistence com SQLAlchemy + SQLite/PostgreSQL
- [ ] API REST + WebSocket (FastAPI)
- [ ] CLI básico (task create/run/status/cancel)

### Médio prazo (Phases 6–7)
- [ ] CLI completo com Rich (progress bars, tabelas, painéis)
- [ ] Git worktree isolation completo
- [ ] GitHub integration (import issues, create PRs)
- [ ] Jira integration (import epics)
- [ ] **Jira agêntico**: worker que monitora o board e cria tasks automaticamente via JQL configurável

### Longo prazo (Phase 8+)
- [ ] Dashboard React (Kanban, task detail, agent monitor, settings)
- [ ] Parallel subtask executor (até 3 simultâneos)
- [ ] Context window continuation (sumarização automática ao atingir 90%)
- [ ] WebFetch/WebSearch tools para pesquisa durante planning
- [ ] Multi-conta com auto-swap em caso de rate limit
- [ ] Notificações (webhook, email) ao completar tasks
