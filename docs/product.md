# CodeForge — Visão de Produto

## O problema

Times de desenvolvimento têm dois gargalos que se reforçam mutuamente.

O primeiro é de **gestão**: ferramentas de PM (Jira, Linear, Notion) são repositórios passivos de texto. Elas capturam o que precisa ser feito, mas não participam da execução. O PM escreve épicos e stories manualmente, a decomposição técnica (quais repos mudar, quais tasks criar) depende de uma reunião de refinamento onde um dev experiente lê tudo e tenta estimar o impacto. É lento, depende de pessoas específicas, e o resultado são tasks mal descritas.

O segundo é de **execução**: mesmo com tasks bem descritas, o trabalho de implementação é repetitivo. Um dev senior gasta grande parte do tempo em tarefas que exigem atenção mas não criatividade — escrever boilerplate, implementar specs já definidas, corrigir code review, ajustar testes. Ferramentas como Copilot e Cursor ajudam, mas o desenvolvedor ainda precisa estar presente conduzindo cada passo.

## A solução

CodeForge é um **sistema operacional para times de desenvolvimento** — uma plataforma que unifica gestão de produto e execução autônoma de código.

O PM trabalha no CodeForge como trabalharia em um Jira, com uma diferença fundamental: a IA é um membro ativo do processo desde o primeiro momento. Ela ajuda a escrever demandas, decompõe stories em tasks técnicas varrendo os repositórios reais, e quando autorizada, executa as tasks autonomamente do início ao fim.

O resultado é um kanban onde cada cartão pode estar sendo trabalhado por um humano, por um agente de IA, ou por ambos em colaboração — e isso é configurável por projeto, por sprint, ou por task individual.

```
PM descreve demanda (com ou sem ajuda da IA)
  → PM cria ou pede para a IA criar os entregáveis (stories)
    → Configura os repositórios e branches do projeto
      → IA varre os repos e cria as tasks técnicas por entregável
        → PM e time definem a sprint — quais entregáveis entram
          → Tasks são executadas: por IA ou por dev
            → Code Review: IA sempre revisa, humano é configurável
              → Done → pipeline de deploy da empresa
```

---

## Atores

### Product Manager
Cria e descreve demandas. Define stories. Configura projetos e sprints. Aprova o breakdown da IA antes de iniciar a execução. Acompanha o progresso no kanban.

### Developer
Pode pegar uma task e trabalhar manualmente (fluxo clássico). Pode atribuir tasks para a IA executar. Faz code review quando necessário. Toma decisões quando a IA precisa de input humano.

### Agente de IA
Participa em todos os estágios onde for autorizado: ajuda a escrever stories, varre repositórios e gera tasks, executa o pipeline de desenvolvimento completo (spec → plan → code → QA), e sempre realiza code review.

---

## Fluxos principais

### 1. Criação da Demanda

O PM abre uma nova **Demanda** (equivalente ao épico). Pode escrever livre ou chamar a IA para ajudar a estruturar com base em uma descrição rasa.

```
PM: "Quero adicionar checkout com PIX no e-commerce"

IA (modo assistente):
  → Sugere estrutura da demanda
  → Propõe critérios de aceitação
  → PM revisa e aprova
```

A Demanda tem: título, objetivo de negócio, critérios de aceitação de negócio, e lista de **Entregáveis**.

### 2. Definição dos Entregáveis (Stories)

Dentro de uma Demanda, o PM cria os **Entregáveis** — cada um representa um pedaço de valor que pode ser entregue e demonstrado independentemente. Novamente, pode escrever direto ou pedir ajuda à IA.

```
Demanda: "Checkout com PIX"

Entregáveis:
  1. Pagamento via PIX (geração de QR Code, confirmação de pagamento)
  2. Conciliação automática (webhook do banco, baixa automática no pedido)
  3. Histórico de transações PIX na conta do usuário
```

### 3. Configuração dos Projetos

O PM vincula à Demanda os repositórios afetados e define a branch base de cada um:

```
Projetos vinculados à demanda:
  - github.com/empresa/backend-api    branch: main
  - github.com/empresa/frontend-web   branch: main
  - github.com/empresa/infra-k8s      branch: staging
```

### 4. Breakdown — IA Varre os Repositórios

Com Entregáveis e Projetos configurados, o PM dispara o **Breakdown**. Para cada Entregável × Projeto, um agente de IA lê o codebase e cria as tasks técnicas necessárias.

```
Entregável: "Pagamento via PIX"
  Agente varre backend-api:
    → Identifica que não existe módulo de pagamento
    → Identifica que existe PaymentService com métodos para cartão
    → Cria tasks:
        - "Criar endpoint POST /payments/pix"
        - "Implementar integração com API do banco (Pix Cob)"
        - "Criar webhook handler para confirmação de pagamento"

  Agente varre frontend-web:
    → Identifica tela de checkout em /src/pages/checkout
    → Cria tasks:
        - "Adicionar opção PIX na tela de pagamento"
        - "Criar componente QRCodeDisplay"
        - "Implementar polling de status de pagamento"
```

O PM vê o breakdown completo antes de qualquer execução. Pode editar, remover, ou adicionar tasks manualmente. Só após aprovação as tasks entram no backlog.

### 5. Sprint Planning

O PM e o time selecionam quais Entregáveis entram na sprint. Todos os Entregáveis selecionados e suas tasks aparecem no Kanban da sprint.

### 6. Execução das Tasks

Cada task pode ser executada de dois modos:

**Modo IA (autônomo):**
O agente executa o pipeline completo:
```
BACKLOG → SPEC → PLANNING → CODING → QA → CODE REVIEW → DONE
```
Cada etapa é uma sessão de agente especializado. O agente trabalha dentro de um git worktree isolado — a branch principal nunca é tocada.

**Modo Humano (manual):**
O dev pega a task, trabalha localmente no seu fluxo normal, abre o PR. O CodeForge rastreia o progresso via status manual ou integração com o repositório.

**Modo Misto:**
O dev começa, chega em um ponto, e pode "passar para a IA" continuar. Ou a IA faz tudo e o dev revisa apenas no code review.

### 7. Code Review

Toda task passa por **Code Review** antes de ir para Done. O comportamento é configurável:

| Configuração | Comportamento |
|---|---|
| `ai_only` | IA revisa, aprova automaticamente se aprovado |
| `human_required` | IA revisa primeiro, depois aguarda aprovação humana |
| `human_optional` | IA revisa, humano pode comentar mas não bloqueia |

Quando `human_required`, a task fica parada em **AWAITING_REVIEW** até um dev do time aprovar.

### 8. Done

Task aprovada no code review → PR mergeado (ou marcado como pronto para merge) → task vai para **Done**. O deploy segue o pipeline de deploy da empresa (CodeForge não gerencia deploy).

---

## O Kanban

O kanban tem dois níveis de visualização:

### Visão por Entregável (PM)

```
Demanda: "Checkout com PIX"
  Entregável: Pagamento via PIX                    ██████░░░░  60%
    [DONE]         backend-api: endpoint POST /payments/pix
    [CODE REVIEW]  frontend-web: componente QRCodeDisplay
    [CODING]       backend-api: integração com API do banco
    [BACKLOG]      frontend-web: polling de status

  Entregável: Conciliação automática               ░░░░░░░░░░   0%
    [BACKLOG]      backend-api: webhook handler
    [BACKLOG]      infra-k8s: configurar ingress webhook
```

### Visão Kanban Clássica (Dev)

```
BACKLOG | SPEC | PLANNING | CODING | QA | CODE REVIEW | DONE
```

Filtrável por: Demanda / Entregável / Responsável (humano ou IA) / Repositório.

---

## Colunas do Kanban e Statusses de Task

```
BACKLOG          — criada, aguardando início
IN_PROGRESS      — alguém pegou (humano ou IA iniciando)
SPEC             — agente escrevendo a especificação técnica
PLANNING         — agente criando o plano de implementação
CODING           — agente implementando (ou dev trabalhando)
QA               — testes automatizados e revisão de qualidade
CODE_REVIEW      — aguardando review (IA sempre, humano se configurado)
AWAITING_REVIEW  — IA aprovou, aguardando aprovação humana
DONE             — task concluída, PR pronto para merge
FAILED           — pipeline falhou, requer intervenção
CANCELLED        — task cancelada
```

---

## Human in the Loop — Pontos de decisão

O CodeForge é configurável em cada ponto onde um humano pode querer intervir:

| Ponto | Configuração | Comportamento padrão |
|---|---|---|
| Aprovação de Entregáveis gerados por IA | `stories_require_approval` | **true** — PM aprova antes de salvar |
| Aprovação de tasks do breakdown | `breakdown_requires_approval` | **true** — PM aprova antes do backlog |
| Início automático de tasks | `auto_start_tasks` | **false** — PM/dev inicia manualmente |
| Code review humano | `human_review_required` | **false** — IA aprova sozinha |
| Merge automático após aprovação | `auto_merge` | **false** — dev faz merge manualmente |

Configurável por Projeto, por Demanda, ou globalmente em `~/.codeforge/config.toml`.

---

## Agentes e seus papéis

| Agente | Thinking | Steps | Quando é usado |
|---|---|---|---|
| `demand_assistant` | medium | 50 | Ajuda PM a estruturar demandas e escrever stories |
| `breakdown` | high | 150 | Varre repos e cria tasks técnicas por entregável |
| `complexity_assessor` | medium | 50 | Avalia SIMPLE/STANDARD/COMPLEX para cada task |
| `spec_writer` | high | 150 | Escreve spec.md a partir da task |
| `spec_critic` | high | 100 | Revisa e corrige a spec |
| `planner` | high | 200 | Cria implementation_plan.json |
| `coder` | medium | 1000 | Implementa subtasks, commita |
| `qa_reviewer` | high | 300 | Roda testes, valida qualidade, escreve qa_report |
| `qa_fixer` | medium | 400 | Corrige issues do QA report |
| `code_reviewer` | high | 200 | Faz code review final do PR |

---

## Entidades do sistema

```
Workspace
  └── Demanda (Epic)
        ├── título, objetivo de negócio, critérios de aceitação
        ├── projetos vinculados (repos + branches base)
        └── Entregável (Story) [1..*]
              ├── título, descrição, critérios de aceitação
              ├── pertence a qual Sprint
              └── Task [1..*]
                    ├── descrição técnica, complexidade
                    ├── projeto (qual repo)
                    ├── assignee: Agent | Human | Unassigned
                    ├── worktree_path, branch_name
                    └── Pipeline completo (Spec, Plan, QA, Review...)

Sprint
  ├── data de início/fim
  ├── entregáveis selecionados
  └── métricas (tasks done/total, story points estimados/concluídos)

Project
  ├── repo_url, default_branch
  ├── CodeReviewConfig (ai_only | human_required | human_optional)
  └── PipelineConfig (max_parallel_subtasks, max_qa_cycles...)
```

---

## Comparativo

| Característica | Jira + Copilot | GitHub Copilot Workspace | CodeForge |
|---|---|---|---|
| Gestão de épicos e stories | Sim | Não | **Sim** |
| Breakdown automático por repositório | Não | Parcial | **Sim** |
| Execução autônoma completa (spec→PR) | Não | Não | **Sim** |
| Human in the loop configurável | Não | Não | **Sim** |
| Code review por IA | Não | Não | **Sim** |
| Dev pode trabalhar manualmente no mesmo board | Sim | Não | **Sim** |
| Isolamento por git worktree | Não | Não | **Sim** |
| Multi-repo por entregável | Não | Não | **Sim** |
| Multi-provider (OpenAI, Anthropic, Gemini...) | Não | Não | **Sim** |

---

## Providers de IA suportados (via LiteLLM)

Qualquer provider compatível: Anthropic, OpenAI, Google Gemini, AWS Bedrock, Azure, Mistral, Groq, Ollama (local), OpenRouter e outros.

Configuração em `~/.codeforge/config.toml`:

```toml
[default]
model = "anthropic:claude-sonnet-4-20250514"

[providers.anthropic]
api_key = "sk-ant-..."

[providers.openai]
api_key = "sk-..."

[providers.ollama]
base_url = "http://localhost:11434"

[pipeline]
human_review_required = false
auto_start_tasks = false
breakdown_requires_approval = true
```

---

## Roadmap de implementação

### Fases 1–4 — COMPLETAS (motor de execução)
Domain layer, tools, security, AI provider, pipelines de spec/build/QA.
213 testes, 0 falhas.

### Fase 5 — Persistence + API REST
SQLAlchemy async + FastAPI. Persiste Task, Project, AgentSession. API REST básica.

### Fase 5B — Domain: Demanda, Entregável, Sprint
Novas entidades de domínio: Demand, Story, Sprint. Novos ports. Migração de Task para incluir story_id/demand_id.

### Fase 6 — CLI
`codeforge demand create`, `codeforge story breakdown`, `codeforge sprint plan`, `codeforge task run`.

### Fase 7 — Agentes de PM + Code Reviewer
`demand_assistant` (ajuda PM), `breakdown` (varre repos), `code_reviewer` (code review final).

### Fase 7B — Git + Integrações
GitService completo (worktree isolation), GitHub Gateway (criar PRs), integração de webhook para status de PR.

### Fase 8 — Dashboard React
Kanban com visão por Entregável e visão clássica. Task detail com pipeline visual + logs em tempo real. Sprint board. Configuração de human-in-the-loop.
