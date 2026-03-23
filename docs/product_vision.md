# CodeForge — Visão de Produto

**Última atualização:** 2026-03-22
**Versão:** 2.0

---

## 1. O Problema

Times de desenvolvimento têm dois gargalos que se reforçam mutuamente.

O primeiro é de **gestão**: ferramentas de PM (Jira, Linear, Notion) são repositórios passivos de texto. Elas capturam o que precisa ser feito, mas não participam da execução. O PM escreve épicos e stories manualmente, a decomposição técnica (quais repos mudar, quais tasks criar) depende de reuniões de refinamento onde um dev experiente lê tudo e tenta estimar o impacto. É lento, depende de pessoas específicas, e o resultado são tasks mal descritas que geram retrabalho.

O segundo é de **execução**: mesmo com tasks bem descritas, o trabalho de implementação é repetitivo. Um dev senior gasta grande parte do tempo em tarefas que exigem atenção mas não criatividade — escrever boilerplate, implementar specs já definidas, corrigir code review, ajustar testes. Ferramentas como Copilot e Cursor ajudam, mas o desenvolvedor ainda precisa estar presente conduzindo cada passo.

O terceiro — menos visível, mais danoso — é de **contexto**: o conhecimento sobre o codebase está fragmentado entre a cabeça dos devs, documentações desatualizadas e threads de Slack. Quando a IA não tem contexto real do repositório, ela gera sugestões genéricas que não servem. Quando o PM não tem visibilidade do que existe no código, ele escreve demandas vagas que precisam de reunião para virar algo executável.

---

## 2. A Solução

CodeForge é uma plataforma que unifica **gestão de produto**, **base de conhecimento** e **execução autônoma de código** em um único ambiente operacional onde Product Managers, desenvolvedores e agentes de IA colaboram no mesmo board.

O PM trabalha no CodeForge como trabalharia no Jira + Confluence, com uma diferença fundamental: a IA é um membro ativo do processo desde o primeiro momento. Ela ajuda a escrever demandas, decompõe stories em tasks técnicas varrendo os repositórios reais usando documentos de contexto gerados automaticamente, e quando autorizada, executa as tasks autonomamente do início ao fim — tudo em git worktrees isolados, sem tocar a branch principal.

O resultado é um fluxo contínuo desde a ideia de produto até o Pull Request:

```
Repositório → Análise (IA) → Documento de Contexto
                                      ↓
PM escreve demanda ──→ IA gera stories precisas ──→ IA decompõe em tasks
                          (referenciando módulos       (referenciando arquivos
                           reais do codebase)           reais, com escopo claro)
                                                              ↓
                                                    Agente executa task
                                                    (worktree isolado)
                                                              ↓
                                                    Spec → Plan → Code → QA
                                                              ↓
                                                    Code Review (IA + humano)
                                                              ↓
                                                    Branch com código pronto
```

Cada cartão do kanban pode estar sendo trabalhado por um humano, por um agente de IA, ou por ambos em colaboração — e isso é configurável por projeto, por sprint, ou por task individual.

---

## 3. Personas

### Product Manager (PM)
Responsável por criar demandas, escrever entregáveis (stories), vincular projetos e planejar sprints. Não tem deep knowledge técnico sobre os repositórios. Precisa de ajuda da IA para escrever com precisão técnica e quer visibilidade do progresso sem precisar perguntar para um dev.

**Dores atuais:** escreve épicos vagos porque não conhece o codebase, precisa de reunião de refinamento para cada demanda, perde tempo em tasks administrativas de decomposição.

### Tech Lead / Desenvolvedor Sênior
Define arquitetura, revisa código, e toma decisões quando a IA trava. Pode pegar tasks manualmente ou deixar a IA executar e revisar apenas o resultado. Quer configurar o nível de autonomia da IA por projeto.

**Dores atuais:** gasta tempo em tarefas repetitivas de implementação, é gargalo para code review, precisa explicar contexto do codebase repetidamente.

### Desenvolvedor
Trabalha tasks do sprint no fluxo clássico (pega task, implementa, abre PR) ou delega para IA e revisa. Quer saber o que está acontecendo nas tasks dos agentes sem precisar abrir logs.

### Agente de IA
Não é uma persona humana, mas é um ator de primeira classe no sistema. Executa tasks autonomamente (spec → plan → código → QA), participa do code review, e pode spawnar sub-agentes para sub-tarefas. Precisa de contexto rico (documento do projeto, task bem descrita, branch isolada).

---

## 4. Pilares do Produto

### Pilar 1 — IA como Membro do Time, Não como Ferramenta

A IA não é um botão de "melhorar texto" em um canto da tela. Ela participa do processo de produto desde a criação da demanda até a aprovação do PR. Cada superfície do produto expõe assistência contextual: o PM recebe sugestões enquanto escreve um épico, a IA usa o contexto real dos repositórios para gerar stories técnicas precisas, e agentes executam tarefas completas autonomamente.

### Pilar 2 — Contexto é Infraestrutura

A IA é tão útil quanto o contexto que ela tem. O Workspace documental (equivalente ao Confluence) é a infraestrutura que alimenta todos os agentes. Documentos de análise de repositório, decisões de arquitetura e documentos de produto não são arquivos mortos — são a memória operacional que torna os agentes mais precisos. Sem contexto, a IA é genérica. Com contexto, ela é um membro do time.

### Pilar 3 — Human-in-the-Loop Configurável

Autonomia não significa ausência de controle. Cada ponto do fluxo onde um humano pode querer intervir é configurável: aprovação de stories geradas pela IA, aprovação do breakdown de tasks antes de entrar no backlog, code review obrigatório por humano. O padrão é conservador (humano aprova tudo), mas times avançados podem abrir a autonomia progressivamente por projeto ou por demanda.

### Pilar 4 — Um Único Ambiente para PM e Dev

PMs e devs não deveriam trabalhar em ferramentas separadas que precisam de sincronização manual. O CodeForge é o sistema onde a demanda nasce, é decomposta, executada e entregue — sem exportar para Jira, sem copiar contexto para Slack, sem reunião de repasse entre o que está escrito no Confluence e o que está no board.

---

## 5. O Diferencial: Pipeline de Automação, Não Assistência de Texto

Todo produto de IA em 2026 "melhora texto". Isso é commodity. O CodeForge não é um assistente de escrita — é um **sistema de automação** que transforma uma ideia de produto em código pronto para review, usando o contexto real dos repositórios do time.

### O que torna a geração PRECISA (não genérica)

A qualidade do output da IA depende de três camadas de contexto:

| Camada | Fonte | Exemplo |
|--------|-------|---------|
| **Contexto técnico** | `Project.context_doc` (análise automática do repo) | "Projeto usa FastAPI, SQLAlchemy async, tem 12 routers, padrão de repository" |
| **Contexto de produto** | Documentos do Workspace (PRDs, ADRs, decisões) | "O módulo de pagamento usa PIX via BCB, precisa de idempotency key" |
| **Contexto da demanda** | Texto do épico + critérios de aceitação | "Usuário precisa ver status do pagamento em tempo real" |

Quando o `story_generator` roda, ele recebe as três camadas. O resultado não é "Implementar feature de pagamento" — é "Criar endpoint POST /api/payments/pix no router payments.py, integrar com BCBClient em infrastructure/integrations/, adicionar modelo PaymentTransaction na persistence, emitir evento PaymentCreated".

Quando o `breakdown_agent` roda, ele varre o codebase real e produz tasks como "Modificar `src/infrastructure/integrations/bcb_client.py` — adicionar método `create_pix_charge()` que chama a API do BCB com idempotency_key".

**Esta precisão é o produto.** Se as stories e tasks geradas não forem melhores do que o que o PM escreveria sozinho, o CodeForge não tem valor.

### Feedback loops que melhoram o output

O sistema não é one-shot. Cada interação do PM refina o resultado:

- **PM rejeita uma story** → sinal de que o contexto estava insuficiente ou a interpretação errada. O sistema registra e ajusta na próxima geração.
- **PM edita uma task** → o breakdown era impreciso. O agente de breakdown aprende o escopo correto.
- **Agente falha numa task** → o QA loop detecta, tenta corrigir. Se falhar 3x, alerta humano. O histórico de falhas alimenta o próximo planejamento.
- **Code review rejeita** → feedback volta para o agente. O padrão de rejeição (ex: "sempre esquece de adicionar testes") vira contexto para futuras execuções.

### IA em tudo, não só na automação

O pipeline de automação é o diferencial, mas a IA deve estar presente em **toda superfície** onde fizer sentido. Melhorar texto de uma demanda, sugerir critérios de aceitação, expandir um documento, traduzir — tudo isso é parte natural do produto.

A distinção é de **prioridade, não de exclusão:**
- O investimento principal vai para a cadeia de automação (contexto → geração → execução)
- A assistência de texto entra naturalmente onde o usuário já está (editor, demanda, story) — é o Pilar 1 ("IA como membro do time")
- A IA nunca vive numa página separada — sempre inline, contextual, acionável

---

## 6. Módulos Funcionais

### 6.1 Dashboard / Home

**O que faz:** Página inicial do time. Visão consolidada do estado atual: sprints ativas, demandas em andamento, tarefas de agentes rodando, alertas de tarefas travadas e atividade recente.

**User stories:**
- Como PM, quero ver de relance quantas tasks estão em andamento, quantas estão travadas e qual é o progresso da sprint atual, para não precisar abrir o kanban para ter essa visibilidade.
- Como desenvolvedor, quero ver as minhas tasks e as tasks dos agentes vinculadas às minhas demandas, para saber o que precisa da minha atenção hoje.
- Como Tech Lead, quero ver tarefas em `FAILED` ou `AWAITING_REVIEW` com destaque, para intervir rapidamente.

**Integração com IA:**
- Painel de resumo gerado por IA: "3 tarefas em code review aguardando sua aprovação, 1 agente travado há 2h na task X."
- Sugestão de próxima ação com base no estado da sprint.

---

### 6.2 Workspace (Base de Conhecimento)

**O que faz:** Espaço documental do time equivalente ao Confluence. Organizado em pastas criadas pelo usuário (não auto-geradas pelo sistema). Suporta documentos em markdown rico. A IA pode ajudar a escrever, melhorar e gerar qualquer documento. Documentos de análise de repositório são gerados automaticamente quando um projeto é analisado e ficam acessíveis aqui.

**Regra de produto:** o sistema nunca cria pastas automaticamente ao criar um time. O usuário tem controle total sobre a estrutura desde o primeiro documento.

**User stories:**
- Como PM, quero criar uma pasta "Arquitetura de Produto" e escrever docs nela com ajuda da IA, para ter a documentação do time organizada da forma que faz sentido para o meu contexto.
- Como PM, quero analisar um repositório e ter o documento de contexto gerado salvo automaticamente no Workspace, para que ele fique disponível como referência nos épicos.
- Como Tech Lead, quero criar um documento de decisão de arquitetura (ADR) com o editor em tela cheia, para documentar decisões importantes com a qualidade que elas merecem.
- Como qualquer membro do time, quero pedir à IA para melhorar ou expandir qualquer documento aberto, para acelerar a escrita sem perder a autoria.

**Integração com IA:**
- Assistente inline no editor: o usuário seleciona um trecho e pede "melhore isso", "expanda com mais detalhes técnicos", "traduza para inglês".
- Geração de documento a partir de repositório: o usuário aponta para um projeto e a IA gera um documento de contexto técnico (stack, estrutura de diretórios, padrões, APIs expostas).
- Geração de documento a partir de template: ADR, RFC, runbook — a IA preenche com base no contexto do time.
- Todo documento do Workspace está disponível como contexto para qualquer agente que trabalhe nas demandas do time.

---

### 6.3 Epics e Backlog de Produto

**O que faz:** Módulo central de gestão de produto. O PM cria Demandas (equivalentes a Épicos), escreve o objetivo de negócio e critérios de aceitação, vincula repositórios afetados, e define Entregáveis (Stories). A IA melhora textos, gera stories a partir da demanda e sugere tasks técnicas varrendo os repositórios.

**User stories:**
- Como PM, quero criar uma demanda descrevendo o objetivo de negócio em linguagem natural e pedir à IA para estruturar com critérios de aceitação, para ter um épico bem escrito sem precisar de um template rígido.
- Como PM, quero vincular um ou mais projetos (repositórios) à demanda, para que a IA saiba qual codebase está no escopo.
- Como PM, quero pedir à IA para gerar entregáveis (stories) a partir da demanda, para ter um breakdown inicial que posso revisar e aprovar antes de entrar no backlog.
- Como PM, quero aprovar, editar ou rejeitar cada entregável gerado pela IA antes que ele entre no backlog, para manter controle editorial sobre o que entra na sprint.
- Como Tech Lead, quero ver o breakdown técnico de tasks por entregável (qual arquivo muda, qual módulo é afetado) antes de aprovar, para garantir que a estimativa é realista.

**Integração com IA:**
- `demand_assistant`: melhora o texto da demanda, sugere critérios de aceitação, identifica ambiguidades.
- `story_generator`: usa o texto da demanda + documentos de contexto dos projetos vinculados para gerar entregáveis tecnicamente precisos.
- `breakdown_agent`: para cada entregável × repositório vinculado, varre o codebase real e gera tasks técnicas com referências a arquivos específicos.
- A qualidade do output aumenta proporcionalmente à qualidade dos documentos de contexto disponíveis no Workspace.

---

### 6.4 Sprint Board (Kanban)

**O que faz:** Gerenciamento de sprints e execução de tasks. O PM seleciona quais entregáveis entram na sprint. Tasks aparecem no kanban com duas visões: por entregável (visão de PM) e kanban clássico por coluna (visão de dev). Tasks podem ser atribuídas a humanos ou agentes de IA.

**Colunas do pipeline:**

```
BACKLOG → IN_PROGRESS → SPEC → PLANNING → CODING → QA → CODE_REVIEW → AWAITING_REVIEW → DONE
```

Estados terminais: `DONE`, `FAILED`, `CANCELLED`.

**Visão por Entregável (PM):**

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

**Visão Kanban Clássica (Dev):**

```
BACKLOG | SPEC | PLANNING | CODING | QA | CODE REVIEW | DONE
```

Filtrável por: Demanda / Entregável / Responsável (humano ou IA) / Repositório.

**User stories:**
- Como PM, quero planejar uma sprint selecionando entregáveis do backlog, para definir o escopo de trabalho de forma visual.
- Como desenvolvedor, quero ver no kanban todas as tasks da sprint com status em tempo real, incluindo as tasks executadas por agentes, para saber o que está acontecendo sem precisar perguntar.
- Como desenvolvedor, quero atribuir uma task a um agente de IA com um clique, para delegar trabalho repetitivo e focar em tarefas que precisam de julgamento humano.
- Como Tech Lead, quero configurar se code review por humano é obrigatório para um projeto específico, para ter controle granular sobre o que vai para produção sem aprovação.
- Como desenvolvedor, quero pegar uma task que o agente começou e continuar manualmente, para situações onde a IA travou e eu prefiro terminar direto.

**Execução de tasks — três modos:**

| Modo | Descrição |
|------|-----------|
| **IA (autônomo)** | Agente executa o pipeline completo: BACKLOG → SPEC → PLANNING → CODING → QA → CODE REVIEW → DONE. Cada etapa é uma sessão de agente especializado. Trabalha em git worktree isolado. |
| **Humano (manual)** | Dev pega a task, trabalha localmente, abre PR. CodeForge rastreia progresso via status manual ou integração com o repositório. |
| **Misto** | Dev começa e passa para IA continuar. Ou IA faz tudo e dev revisa no code review. |

**Integração com IA:**
- Execução autônoma: o agente passa por todas as fases do pipeline sem intervenção humana, exceto nos pontos de aprovação configurados.
- Code review por IA: mesmo em tasks executadas por humanos, a IA pode fazer o primeiro round de review.
- Detecção de bloqueios: a IA identifica quando uma task está em loop (ex: QA reprovando pela terceira vez) e alerta o time.

---

### 6.5 Gerenciamento de Projetos (Repositórios)

**O que faz:** Cadastro e gerenciamento de repositórios vinculados ao time. Dois fluxos de entrada: caminho local (para projetos na máquina do usuário) ou URL de repositório remoto. A IA analisa o repositório automaticamente após o cadastro e gera um documento de contexto. Projetos com contexto disponível aparecem com badge de status nas demandas.

**User stories:**
- Como Tech Lead, quero adicionar um repositório pelo caminho local ou URL, para que ele fique disponível para ser vinculado a demandas.
- Como Tech Lead, quero disparar a análise de um repositório e acompanhar o progresso em tempo real via streaming, para saber quando o documento de contexto estará pronto.
- Como PM, quero ver quais projetos já têm documento de contexto gerado ao vincular projetos a uma demanda, para saber se a IA terá informações suficientes para gerar stories precisas.
- Como Tech Lead, quero escolher qual executor de IA usar para analisar o repositório (Claude Code, Gemini CLI, etc.), para usar o executor mais adequado ao tamanho e complexidade do projeto.

**Integração com IA:**
- Análise via skills (`analyze-with-claude`, `analyze-with-gemini`, `analyze-with-opencode`): o skill executa o executor escolhido em modo subprocess, varre o repositório e gera um documento markdown estruturado com stack, estrutura, padrões, APIs, dependências externas e pontos de atenção.
- O documento de contexto gerado é salvo em `Project.context_doc` e também como documento navegável no Workspace do time.
- Reanálise: o usuário pode solicitar uma nova análise após mudanças significativas no projeto.

---

### 6.6 Orquestrador de Agentes

**O que faz:** Painel de monitoramento e controle dos agentes em execução. Mostra sessões ativas, logs em tempo real, uso de tokens, taxa de sucesso, e permite intervenções manuais (pausar, cancelar, retomar).

**User stories:**
- Como Tech Lead, quero ver todos os agentes rodando no momento com seu status, task associada e tempo de execução, para ter visibilidade do que está consumindo recursos.
- Como desenvolvedor, quero ver os logs de uma sessão de agente em tempo real, para entender o que ele está fazendo e intervir se necessário.
- Como Tech Lead, quero cancelar um agente que está em loop ou travado, para liberar recursos e realocar a task para um humano.
- Como Tech Lead, quero ver o histórico de sessões de agentes com taxa de sucesso por tipo de task, para calibrar quando faz sentido usar agentes e quando é mais eficiente delegar a humanos.

**Métricas exibidas:**
- Sessões ativas e na fila
- Tokens consumidos (por sessão, por task, por sprint)
- Taxa de sucesso (tasks completadas / tasks iniciadas)
- Tempo médio por fase do pipeline

---

### 6.7 Configurações

**O que faz:** Configurações do time e do sistema.

**Seções:**
- **GitHub App:** Conexão com repositórios via GitHub App (fluxo tipo Claude — botão único "Conectar GitHub", sem credentials manuais). Admin configura o App uma vez; usuário só autoriza repos.
- **Providers de IA:** adicionar e testar chaves de API (Anthropic, OpenAI, Gemini, Ollama, etc.) — qualquer provider compatível via LiteLLM
- **Modelos:** definir modelo padrão por tipo de agente (ex: Claude Sonnet para breakdown, Gemini para análise de repos grandes)
- **Human-in-the-loop:** configurações globais de aprovação — quando a IA precisa de aprovação humana
- **Time:** gerenciar membros, permissões
- **Executores:** verificar quais CLIs de IA estão disponíveis na máquina (Claude Code, Gemini CLI, OpenCode)
- **Workspace local:** pasta base para localizar repositórios na máquina

---

## 7. Agentes do Sistema

Cada agente é especializado em uma fase do pipeline e configurado com thinking level, step budget e tools específicas.

| Agente | Papel | Thinking | Steps | Tools |
|--------|-------|----------|-------|-------|
| `demand_assistant` | Ajuda PM a estruturar demandas e escrever stories | medium | 50 | Read, Glob, Grep |
| `story_generator` | Gera stories tecnicamente precisas usando contexto do repo | high | 150 | Read, Glob, Grep |
| `breakdown` | Varre repos e cria tasks técnicas por entregável | high | 150 | Read, Glob, Grep |
| `complexity_assessor` | Avalia SIMPLE/STANDARD/COMPLEX para cada task | medium | 50 | Read, Glob, Grep |
| `spec_writer` | Escreve spec.md a partir da task | high | 150 | Read, Glob, Grep, Write, WebFetch, WebSearch |
| `spec_critic` | Revisa e corrige a spec | high | 100 | Read, Glob, Grep, Write |
| `planner` | Cria implementation_plan.json | high | 200 | todos (incl. Exec) |
| `coder` | Implementa subtasks, commita | medium | 1000 | todos (incl. Exec) |
| `qa_reviewer` | Roda testes, valida qualidade, escreve qa_report | high | 300 | Read, Glob, Grep, Write, Edit, Bash, Exec |
| `qa_fixer` | Corrige issues do QA report | medium | 400 | Read, Glob, Grep, Write, Edit, Bash, Exec |
| `code_reviewer` | Faz code review final do PR | high | 200 | Read, Glob, Grep |

---

## 8. Entidades do Sistema

```
Workspace
  ├── Team
  │     ├── membros, permissões
  │     └── Documentos do Workspace (pastas, docs markdown)
  │
  └── Demanda (Epic)
        ├── título, objetivo de negócio, critérios de aceitação
        ├── projetos vinculados (repos + branches base + context_doc)
        └── Entregável (Story) [1..*]
              ├── título, descrição, critérios de aceitação
              ├── pertence a qual Sprint
              └── Task [1..*]
                    ├── descrição técnica, complexidade (SIMPLE | STANDARD | COMPLEX)
                    ├── projeto (qual repo)
                    ├── assignee: Agent | Human | Unassigned
                    ├── worktree_path, branch_name
                    └── Pipeline (Spec, Plan, Code, QA, Review...)

Sprint
  ├── data de início/fim
  ├── entregáveis selecionados
  └── métricas (tasks done/total, story points estimados/concluídos)

Project
  ├── repo_url ou local_path, default_branch
  ├── context_doc (análise automática do repo)
  ├── CodeReviewConfig (ai_only | human_required | human_optional)
  └── PipelineConfig (max_parallel_subtasks, max_qa_cycles...)
```

---

## 9. Human-in-the-Loop — Pontos de Decisão

O CodeForge é configurável em cada ponto onde um humano pode querer intervir:

| Ponto | Configuração | Padrão |
|-------|-------------|--------|
| Aprovação de stories geradas por IA | `stories_require_approval` | **true** — PM aprova antes de salvar |
| Aprovação de tasks do breakdown | `breakdown_requires_approval` | **true** — PM aprova antes do backlog |
| Início automático de tasks | `auto_start_tasks` | **false** — PM/dev inicia manualmente |
| Code review humano | `human_review_required` | **false** — IA aprova sozinha |
| Merge automático após aprovação | `auto_merge` | **false** — dev faz merge manualmente |

Configuração por code review:

| Modo | Comportamento |
|------|--------------|
| `ai_only` | IA revisa, aprova automaticamente se aprovado |
| `human_required` | IA revisa primeiro, depois aguarda aprovação humana |
| `human_optional` | IA revisa, humano pode comentar mas não bloqueia |

Configurável por Projeto, por Demanda, ou globalmente.

---

## 10. Fluxos Principais (User Journeys)

### Fluxo 1 — Onboarding: Primeiro Time até Primeiro Épico

```
1. Usuário cria um time (nome, sem pastas auto-geradas)
2. Vai para Settings → adiciona chave de API + verifica executores disponíveis
3. Vai para Workspace → cria uma pasta "Projetos" (escolha do usuário)
4. Clica em "Adicionar Projeto" → informa caminho local ou URL do repo
5. Sistema detecta executores disponíveis, usuário escolhe qual usar para análise
6. Análise roda via subprocess com streaming de logs em tempo real
7. Documento de contexto salvo em Project.context_doc + documento no Workspace
8. Usuário vai para Demands → cria primeira demanda
9. Vincula o projeto recém-analisado (badge verde "contexto disponível")
10. Clica "Gerar Stories" → IA usa contexto do projeto + texto da demanda
11. Stories aparecem em streaming, usuário aprova/edita/rejeita
12. Demanda está pronta para planejamento de sprint
```

### Fluxo 2 — Épico até Execução Autônoma

```
1. PM escreve demanda (título + objetivo de negócio)
2. PM clica "Melhorar com IA" → demand_assistant sugere critérios de aceitação
3. PM vincula projetos ao épico (todos com contexto disponível)
4. PM clica "Gerar Stories" → story_generator cria entregáveis técnicos via SSE
5. PM revisa e aprova cada story (ou edita antes de aprovar)
6. PM clica "Gerar Tasks" por story → breakdown_agent varre cada repositório vinculado
7. Breakdown mostra tasks com referências a arquivos reais
8. PM (ou Tech Lead) aprova o breakdown → tasks entram no backlog
9. Sprint planning: PM seleciona entregáveis para a sprint
10. Dev (ou PM) clica "Executar com IA" em tasks elegíveis
11. Agente inicia: SPEC → PLANNING → CODING → QA → CODE_REVIEW
12. Se human_review_required=true: task fica em AWAITING_REVIEW
13. Dev revisa o PR, aprova → task vai para DONE
```

### Fluxo 3 — Análise de Repositório

```
1. Usuário adiciona projeto (caminho local ou URL remota)
2. Sistema verifica quais skills de análise estão disponíveis (Claude Code, Gemini CLI, OpenCode)
3. Usuário seleciona executor e clica "Analisar"
4. Backend spawna subprocess com o executor escolhido
5. Logs fluem em tempo real via SSE para o frontend
6. Ao concluir: context_doc salvo no banco (Project.context_doc)
7. Documento markdown também salvo no Workspace do time
8. Badge do projeto muda de "Sem contexto" para "Contexto disponível"
9. Próximo épico vinculado a este projeto terá acesso ao contexto
```

### Fluxo 4 — Colaboração em Documento no Workspace

```
1. Tech Lead cria pasta "Arquitetura" no Workspace do time
2. Clica "Novo Documento" → abre editor em tela cheia (estilo Notion)
3. Escreve rascunho de ADR (Architecture Decision Record)
4. Seleciona um parágrafo e usa ação inline "Melhorar com IA"
5. IA expande o contexto usando documentos do Workspace como referência
6. Tech Lead revisa, aceita ou rejeita as sugestões
7. Salva documento → disponível como contexto para todos os agentes do time
```

### Fluxo 5 — Execução de Sprint com Agentes

```
1. Sprint planejada com N entregáveis e M tasks
2. Dev abre o kanban → visão clássica ou visão por entregável
3. Tasks com assignee "Unassigned" podem ser atribuídas a humano ou agente
4. Para tasks simples e bem contextualizadas: "Executar com IA"
5. Agente inicia em background → task move para IN_PROGRESS → SPEC → PLANNING...
6. Dev acompanha progresso no kanban (status atualiza em tempo real)
7. Dev pode abrir o painel do agente para ver logs detalhados a qualquer momento
8. Tasks em FAILED aparecem com destaque → dev intervém (pega manualmente ou cancela)
9. Ao final da sprint: métricas de tasks done por humano vs por IA, taxa de sucesso dos agentes
```

---

## 11. Princípios de UX

### Sem pastas auto-geradas
O sistema nunca cria estrutura de pastas automaticamente ao criar um time. O usuário começa com uma área limpa e cria a estrutura que faz sentido para ele.

### Editor em tela cheia
Qualquer documento no Workspace abre em modo de edição que ocupa toda a área disponível, sem sidebar ou painéis competindo por espaço. O foco é o conteúdo.

### IA como assistente inline, não como página separada
O usuário não "vai para a IA". A IA vem até onde o usuário está. No editor de demandas: botão "Melhorar" ao lado do campo. No breakdown: "Gerar tasks" por entregável. No kanban: "Executar com IA" no card. Nunca um modal separado de "chat com IA" que quebra o fluxo.

### Streaming primeiro
Toda operação de IA que leva mais de 2 segundos deve mostrar progresso em tempo real. Logs fluindo, texto aparecendo palavra a palavra, barra de progresso — qualquer feedback é melhor que uma tela congelada.

### Progressive disclosure
Usuários novos não veem todas as configurações avançadas. As defaults são conservadoras e funcionam. Configurações avançadas ficam em seções colapsáveis, acessíveis quando o usuário precisar.

### Aprovação explícita antes de execução
A IA nunca executa código ou commita sem aprovação explícita. Stories geradas ficam em estado "Proposta" até o PM aprovar. O breakdown de tasks fica em "Aguardando Aprovação" até review. O usuário nunca acorda com um PR que ele não autorizou.

---

## 12. Métricas de Sucesso

### Métricas de produto

| Métrica | Descrição |
|---------|-----------|
| Taxa de aprovação de stories geradas por IA | % de stories geradas que foram aprovadas sem edição significativa |
| Taxa de aprovação de breakdowns gerados por IA | % de tasks do breakdown aprovadas sem edição |
| Taxa de sucesso de execução autônoma | % de tasks executadas por agentes que chegaram a DONE sem intervenção humana |
| Tempo médio por fase do pipeline | Quanto tempo cada agente passa em cada fase (SPEC, PLANNING, CODING, QA) |
| Tokens por task | Custo de IA por task concluída, segmentado por tipo de agente |
| Retrabalho pós code review | % de tasks que voltaram de CODE_REVIEW para CODING mais de uma vez |

### Métricas de adoção

| Métrica | Sinal positivo |
|---------|---------------|
| % de tasks com agente em sprints ativas | Time confia na IA para executar |
| Número de documentos criados no Workspace | Times estão usando como Confluence real |
| Tempo entre criação da demanda e primeiro PR | Velocidade do ciclo completo |
| NPS do PM após 30 dias | Produto entrega valor percebido para quem cria as demandas |

---

## 13. Análise de Mercado

### O gap que o CodeForge ocupa

O mercado está dividido em dois mundos que não se tocam:

**Mundo PM** — Jira, Linear, Notion, Plane, Huly. Excelentes em gestão de projetos. Zero execução de código. A IA nesses produtos sumariza issues, sugere prioridades, gera texto — nunca toca no codebase.

**Mundo AI Coding** — Devin, OpenHands, Factory AI, GitHub Copilot Workspace, Google Jules, Sweep, Cosine. Executam código autonomamente a partir de issues/prompts. Zero gestão de projetos. Nenhum tem kanban, sprints, épicos ou base de conhecimento.

**Nenhuma ferramenta no mercado unifica PM + Knowledge Base + Execução Autônoma de Código.** O mais próximo seria usar Jira + Confluence + Devin separadamente — três produtos sem integração profunda, sem a inteligência de gerar tasks técnicas a partir da análise real do código.

### O que ninguém faz

1. **Epic → Stories técnicas via análise real do codebase.** Nenhuma ferramenta pega um épico e analisa o código real para gerar stories como "Criar modelo User em /src/models/user.py".
2. **Kanban → Agente executa a task.** Nenhuma permite clicar "Executar com IA" em um card e ter um agente executando spec → plan → code → QA → review.
3. **Knowledge base que alimenta agentes.** Nenhuma tem docs/wiki que são automaticamente usados como contexto pelos agentes de coding.
4. **Monitor centralizado de agentes.** Nenhuma oferece dashboard onde se vê todos os agentes trabalhando em paralelo com logs, tokens, success rate e capacidade de intervir.
5. **Human-in-the-loop granular.** Nenhuma permite configurar "para este projeto exijo review humano, para aquele a IA decide sozinha".

### Comparativo detalhado

| Capacidade | Jira + Confluence | Linear | Devin | GitHub Copilot WS | Factory AI | OpenHands | CodeForge |
|---|---|---|---|---|---|---|---|
| PM completo (épicos, stories, sprints) | **Sim** | **Sim** | -- | Fraco | -- | -- | **Sim** |
| Knowledge base integrada | **Sim** (separado) | -- | -- | -- | -- | -- | **Sim** |
| Análise de codebase → tasks técnicas | -- | -- | Parcial | **Sim** | **Sim** | Parcial | **Sim** |
| Execução autônoma (spec→PR) | -- | -- | **Sim** | Semi | Parcial | **Sim** | **Sim** |
| Human-in-the-loop configurável | -- | -- | Limitado | **Sim** | **Sim** | Configurável | **Sim** |
| Code review por IA | -- | -- | Via PR | Via PR | **Sim** | Via PR | **Sim** (integrado) |
| Dev trabalha no mesmo board | **Sim** | **Sim** | -- | -- | -- | -- | **Sim** |
| Multi-repo por entregável | Link | Link | Limitado | -- | **Sim** | Básico | **Sim** |
| Multi-provider IA | -- | -- | -- | -- | -- | **Sim** | **Sim** |
| Contexto do repo → geração precisa | -- | -- | Parcial | Parcial | **Sim** | Parcial | **Sim** |
| Monitor de agentes real-time | -- | -- | Básico | -- | **Sim** | **Sim** | **Sim** |
| Isolamento por git worktree | -- | -- | Sandbox | -- | -- | Docker | **Sim** |

### Competidores por categoria

**AI Coding Agents:**
- **Devin** (Cognition AI) — ~$500/mês. Primeiro "AI software engineer". Executa tasks em sandbox, mas zero PM. Recebe task isolada, não tem visão de sprint.
- **OpenHands** — Open-source (ex-OpenDevin). Agente autônomo com terminal/editor/browser em Docker. Bom para execução, mas sem gestão.
- **Factory AI** — "Droids" especializados (code review, migrations, testing). Enterprise. Integra com Jira/Linear mas não é PM próprio.
- **GitHub Copilot Workspace** — Semi-autônomo dentro do GitHub. PM rudimentar (GitHub Projects). Cada passo requer aprovação humana.
- **Google Jules** — Resolve bugs/features a partir de issues do GitHub. Roda em VM na nuvem. Sem PM.
- **Sweep AI** — Bot que transforma issues em PRs. Escopo limitado a mudanças menores.
- **Cosine/Genie** — Entendimento profundo de codebase via embeddings. Issue→PR autônomo.
- **Amazon Q Developer** — Forte em migrations (Java 8→17). Semi-autônomo para features.

**PM com IA:**
- **Jira + Atlassian Intelligence** — PM enterprise dominante. IA sumariza e categoriza. Rovo AI faz busca e automação de workflows — não executa código.
- **Linear** — PM moderno e rápido. IA para auto-categorização e drafts. Zero execução.
- **Notion AI** — Workspace all-in-one. IA gera texto e responde sobre docs. PM básico (sem sprints nativos).
- **Plane.so** — Alternativa open-source ao Jira. Zero IA.
- **Huly.io** — All-in-one open-source (PM + docs + chat). Zero IA de coding.

### Risco competitivo

O risco principal não é um competidor direto (ninguém faz o que o CodeForge propõe), mas a **convergência dos incumbentes:**
- **GitHub** pode evoluir Copilot Workspace + Projects para cobrir PM + coding.
- **Atlassian** pode evoluir Rovo AI de automação de workflows para execução de código.
- **Cognition** (Devin) pode adicionar gestão de projetos.

A vantagem do CodeForge é ser **native-integrated** desde o dia 1 — PM, knowledge base e execução autônoma desenhados juntos, não colados depois.

---

## 14. O Que NÃO É o CodeForge

**Não é um substituto para Claude Code, Aider ou Cursor.** O CodeForge orquestra esses executores, não compete com eles. O executor é o que escreve o código. O CodeForge decide *o que* executar, *quando*, em *qual repositório*, e *com qual contexto*.

**Não gerencia infraestrutura ou deploy.** O CodeForge abre PRs. O que acontece depois do merge é responsabilidade da pipeline de deploy da empresa.

**Não é uma ferramenta de chat.** Não há uma interface de chat livre com IA. Toda interação com IA é contextual e acionável: melhorar um texto, gerar stories, executar uma task.

**Não é um IDE.** O editor do Workspace é para documentação, não para código. Código é editado pelo executor de IA no repositório local.

**Não é uma ferramenta de analytics de engenharia.** Métricas de DORA e análise de produtividade não estão no escopo. O CodeForge mostra progresso da sprint e custo dos agentes.

**Não substitui o code review humano em projetos críticos.** O code review de IA é um primeiro filtro, não a palavra final.

---

## 15. Integrações Externas (Futuro — Fora do Foco Atual)

Integrações com ferramentas externas só fazem sentido quando o core funciona bem. Um canivete que não corta não precisa de saca-rolhas.

**Pré-requisito para qualquer integração:** O pipeline completo (demanda → stories → tasks → execução → código em branch) funciona end-to-end dentro do CodeForge sem depender de nenhuma ferramenta externa.

**Quando considerar (não agora):**
- **GitHub/GitLab:** Criar PR automaticamente, webhooks de status, importar issues. Só quando o agente já produz código em branches.
- **Jira:** Importar épicos existentes, sync bidirecional. Só quando times com Jira legado querem migrar.
- **Slack/Teams:** Notificações de tasks travadas, resumo de sprint. Só quando há sprint real com agentes rodando.
- **CI/CD:** Ler status de pipeline para informar o board. Só quando há PRs reais sendo mergeados.

---

## 16. Roadmap de Alto Nível

O roadmap detalhado com checklists está em `docs/roadmap.md`.

### Foco atual — Fazer o canivete cortar

O CodeForge tem motor backend robusto (pipelines, tools, AI provider, 438+ testes) e frontend com múltiplas views. Mas a experiência está fragmentada e o pipeline de automação não está conectado end-to-end na UI. **Nenhuma integração externa faz sentido até o core funcionar bem.**

### Fase 1 — Fundação UX
Corrigir a experiência base: validação de projetos, editor full-width, filtros por time, onboarding guiado, CRUD completo de demandas/stories. O PM consegue usar o produto sem adivinhar.

### Fase 2 — Pipeline de Geração Precisa
Tornar a geração de stories e tasks **precisa, não genérica**. Stories referenciam módulos reais. Tasks apontam para arquivos específicos. O PM vê qual contexto alimentou a geração. Aprova, rejeita e ajusta artefatos individualmente. É aqui que o produto se diferencia de qualquer "chat com IA".

### Fase 3 — Pipeline de Execução Autônoma
Agentes executam tasks em git worktrees isolados. Botão "Executar com IA" no kanban. Pipeline completo (spec → plan → code → QA → review) visível em tempo real. Resultado: código real em branch separada, pronto para review humano.

### Fase 4 — Visibilidade e Controle
Sprint planning funcional. Monitor de agentes em tempo real. Métricas de custo e sucesso. Human-in-the-loop configurável na UI. Dashboard com alertas de tasks travadas.

### Futuro — Só quando o core estiver afiado
Multi-usuário real, GitHub/Jira/Slack, cloud execution. Nada disso entra no roadmap ativo até que o pipeline completo (demanda → código em branch) funcione end-to-end para um usuário solo.

---

*Este documento é o referencial de produto para o CodeForge. Decisões de desenvolvimento devem ser avaliadas contra os pilares, personas e princípios de UX descritos aqui — especialmente a seção 5 (Pipeline de Automação). Quando uma feature proposta não se encaixar em nenhum módulo descrito ou contradizer o que o produto não é (seção 14), é um sinal para questionar antes de implementar.*
