# KodeJutso — Roadmap de Produto

**Data:** 2026-03-23
**Baseado em:** `docs/product_scope.md` v1.0
**Estado atual:** 438 testes passando, TypeScript limpo, backend funcional, Fase 1 completa (exceto GitHub App que depende de criacao do App), Fase 2 completa

---

## Diagnostico: onde estamos

O KodeJutso tem um backend robusto (domain layer completo, 13 entidades, 10 use cases,
pipelines de Spec/Build/QA, skills system, AI provider multi-modelo) e um frontend com
7 views. A reestruturacao do Workspace (Fase 1 parcial) esta concluida — projetos e
repositorios sao nodes de primeira classe na arvore. O GitHub App esta parcialmente
implementado no backend mas o frontend precisa ser simplificado para fluxo tipo Claude.

### O que funciona end-to-end
- Criar time, adicionar projeto (com path local), disparar analise, ver context_doc
- Criar demanda manual ou com IA, vincular projetos, gerar stories via SSE
- Kanban basico com colunas, criar tasks, visualizar detalhes
- Workspace com arvore hierarquica unificada (projetos e repos como nodes com icones)
- Criar pastas/documentos em qualquer nivel da arvore (dentro de projetos, repos, etc.)
- Editar documentos com MDXEditor
- Monitor de agentes (visualizacao de sessoes passadas)
- Settings com chaves de API, workspace local, e endpoints de GitHub App (PUT/DELETE)
- Reconciliacao automatica de pastas de projetos/repos no Workspace
- Auto-migration do Alembic no startup (PostgreSQL e SQLite)

### O que foi resolvido recentemente

| Item | Status |
|------|--------|
| Projetos/repos como nodes de primeira classe no Workspace | Feito |
| `linked_repository_id` em TeamDocument + migration 0014 | Feito |
| Reconciliacao de pastas no GET workspace | Feito |
| Auto-criacao de pastas ao criar/editar projeto/repo | Feito |
| DELETE route para team-documents | Feito |
| SettingsView simplificado (removido tabs Projeto/Repositorios) | Feito |
| Auto-migration no startup para PostgreSQL | Feito |
| PUT/DELETE endpoints para GitHub App credentials | Feito |
| Frontend API functions para save/delete GitHub App | Feito |
| Editar projeto (inline rename no header, syncs folder title) | Feito |
| Deletar projeto (inline confirmation com cascade warnings) | Feito |
| Editor Confluence-quality (admonitions, diff source, frontmatter, images, 23 langs) | Feito |
| Full-width editor (removido max-w-3xl, padding 24px 32px) | Feito |
| mdxeditor-dark.css expandido (425→500+ linhas, dark theme completo) | Feito |
| Demanda editavel (inline title/objective/criteria + "Melhorar com IA") | Feito |
| Stories editaveis via EditStoryModal (title, description, criteria, refs, project, repos) | Feito |
| Stories aprovar/rejeitar individual (proposed → backlog/rejected) | Feito |
| Deletar demanda com confirmacao inline (cascade warning, sem window.confirm) | Feito |
| Deletar story com confirmacao inline | Feito |
| Regenerar stories (botao muda label quando stories existem) | Feito |
| Story status badges coloridos com labels em portugues | Feito |
| StoryRow com icons nos botoes e melhor hierarquia visual | Feito |
| Corrigido import nao usado (ChangeAdmonitionType) no MarkdownEditor | Feito |

### O que ainda precisa de atencao

| Problema | Onde | Impacto | Fase |
|----------|------|---------|------|
| GitHub App wizard pede credentials ao usuario | SettingsView | Deve ser botao simples como Claude | 1 (depende de criar App) |
| Nenhuma validacao de path/repo ao adicionar | AddProjectPanel | Projeto adicionado com path invalido nao da erro | 1 (parcial) |
| Repos remotos/privados ignorados | AddProjectPanel | Sem clone, sem check de auth, sem SSH | 4 |
| Nao da pra executar task com IA pela UI | KanbanView | Pipeline backend existe, UI nao | 3 |
| Sem human-in-the-loop configuravel na UI | SettingsView | Toggles sao read-only | 3 |

---

## Principios deste roadmap

1. **Experiencia primeiro, feature depois.** Nao adianta ter pipeline de execucao
   autonoma se o PM nao consegue adicionar um projeto sem adivinhar.

2. **Cada fase entrega um fluxo completo.** Nenhuma fase termina com "backend pronto,
   UI pendente". Cada fase tem criterio de done do ponto de vista do usuario.

3. **Time e a unidade central.** Tudo filtra por time. Demandas, projetos, sprints,
   documentos, agentes — tudo pertence a um time.

4. **IA e inline, nunca separada.** Nenhuma feature de IA vive numa pagina propria.
   Ela aparece onde o usuario esta: no editor, no card de demanda, no kanban.

5. **Autonomia progressiva.** Comecamos com humano aprovando tudo. Cada fase abre
   mais autonomia para os agentes, sempre configuravel.

---

## Fase 1 — Fundacao de Experiencia

**Objetivo:** Um PM consegue criar um time, mapear repositorios, analisa-los,
organizar documentos e criar epicos com contexto — tudo num fluxo claro e guiado,
sem adivinhar.

**Duracao estimada:** Esta fase e pre-requisito para tudo. Sem ela, o produto nao
e usavel por ninguem que nao seja o desenvolvedor.

### 1.0 Workspace reestruturado (CONCLUIDO)

**Problema:** Projetos e repositorios estavam enterrados em tabs do Settings.
O Workspace nao mostrava a relacao entre projetos, repos e documentos.

**Entregas realizadas:**
- Projetos sao nodes de primeira classe na arvore (icone Layers, cor indigo)
- Repositorios sao nodes de primeira classe na arvore (icone GitBranch, cor emerald)
- `linked_repository_id` adicionado ao `TeamDocument` + migration 0014
- 4 novos metodos no domain port: `list_by_repository`, `find_generated_repo_context_document`,
  `find_folder_for_project`, `find_folder_for_repository`
- Reconciliacao automatica: GET workspace cria pastas faltantes para projetos/repos
- Auto-criacao de pastas ao criar/editar projeto (POST/PATCH) e ao criar repo
- DELETE route para team-documents
- SettingsView simplificado: removido tabs Projeto/Repositorios (vivem no Workspace agora)
- DocumentsView reescrito (~1308 linhas) com arvore unificada

### 1.0b GitHub App — simplificar para fluxo tipo Claude (PENDENTE)

**Problema:** O wizard de 3 etapas pede ao usuario para colar App ID, slug e
private key. Isso e trabalho de admin, nao de usuario. O fluxo correto e
o usuario clicar um botao e autorizar repos, como no Claude.

**Pre-requisito:** Admin precisa criar o GitHub App "KodeJutso" no GitHub
(ver `docs/github_app_setup.md`).

**Entregas:**
- Simplificar SettingsView: remover wizard de 3 etapas com campos de credentials
- Se App nao configurado (`configured=false`): mostrar mensagem para admin
- Se App configurado (`configured=true`): mostrar botao "Conectar GitHub"
  que abre `github.com/apps/{slug}/installations/select_target`
- Manter endpoints PUT/DELETE para uso administrativo (nao exposto na UI)
- Backend: zero mudancas necessarias (endpoints ja existem)

**Criterio de done:** Usuario clica "Conectar GitHub", e redirecionado para
pagina de instalacao do GitHub, escolhe repos, volta. Zero fields para preencher.

### 1.1 Projeto: adicionar, validar, editar, deletar

**Problema:** Adicionar projeto e um formulario escondido que nao valida nada.

**Entregas:**
- Mover "Adicionar Projeto" para acao de primeira classe no Workspace (botao visivel
  com label, nao icone oculto na toolbar)
- Formulario de projeto redesenhado:
  - Campo "Path local": validacao no backend (`os.path.isdir`, verifica se e git repo)
  - Campo "URL do repositorio": validacao de formato, check de acessibilidade
  - Se URL fornecida sem path local: opcao de clonar (precisa de GITHUB_TOKEN ou SSH key)
  - Feedback claro de erros ("Path nao encontrado", "Nao e um repositorio git",
    "Repositorio privado — configure GITHUB_TOKEN em Settings")
- Tela de detalhe de projeto (acessivel do Workspace e do Dashboard):
  - Nome, path, URL, time vinculado, status de analise, executor usado
  - Botoes: Editar, Deletar, Analisar/Reanalisar
  - Viewer do context_doc (MarkdownViewer, nao `<pre>`)
- API: `PATCH /api/projects/{id}`, `DELETE /api/projects/{id}` (com validacao de
  cascata — nao deletar projeto vinculado a demandas ativas)
- Ao adicionar projeto remoto sem token: warning com link direto para Settings > Chaves

**Criterio de done:** PM adiciona repo por path local, sistema valida que e git repo,
mostra confirmacao. PM tenta adicionar path invalido, sistema mostra erro claro. PM
adiciona URL de repo privado sem token, sistema avisa e direciona para Settings.

### 1.2 Analise de repositorio conectada ao Workspace

**Problema:** Analise salva context_doc no banco mas nao cria documento navegavel
no Workspace. O PM nao ve o resultado onde espera (na arvore de documentos).

**Entregas:**
- `run_project_analysis` modificado: alem de salvar em `Project.context_doc`, cria
  (ou atualiza) um `TeamDocument` com `source=generated`, `linked_project_id` e
  `parent_id` apontando para uma pasta do projeto (criada automaticamente se nao existir
  — esta e a unica criacao automatica de pasta permitida: quando o usuario pede
  explicitamente para analisar um projeto)
- Documento gerado aparece imediatamente na arvore do Workspace apos analise
- Badge no Workspace mostra "Atualizado em {data}" para docs gerados
- Reanalisar atualiza o documento existente, nao cria novo

**Criterio de done:** PM clica "Analisar" num projeto, analise roda com SSE, ao
concluir o documento de contexto aparece na arvore do Workspace imediatamente,
navegavel e renderizado em markdown.

### 1.3 Editor full-width e consistente

**Problema:** Editor tem max-w-4xl, contradizendo principio de UX.

**Entregas:**
- Remover `max-w-4xl` do container do editor no DocumentsView
- Revisar todas as superficies que usam MarkdownViewer para consistencia:
  - SettingsView: trocar `<pre>` por MarkdownViewer
  - DemandDetailView: ja usa MarkdownViewer — ok
- Editor do Workspace deve ocupar toda a area disponivel

**Criterio de done:** Documento aberto no Workspace ocupa toda a largura do painel
direito, sem margens artificiais.

### 1.4 Filtros por time em todas as views

**Problema:** Demandas e kanban nao filtram por time. Sidebar tem seletor de time
mas ele so afeta o Workspace.

**Entregas:**
- `ProductView`: `getDemands(teamId)` — filtrar por time ativo
- `KanbanView`: remover dependencia de `activeProjectId`. Tasks filtradas por
  sprint ativa do time (nao por projeto individual)
- `AgentMonitorView`: filtrar sessoes por time
- API: `GET /api/demands?team_id={id}`, `GET /api/tasks?team_id={id}` (novos filtros)
- Quando time muda no sidebar, todas as views recarregam

**Criterio de done:** PM troca de time no sidebar, todas as telas mostram dados
do time correto. Demandas de outro time nao aparecem.

### 1.5 Onboarding guiado

**Problema:** PM chega numa tela vazia sem saber o que fazer.

**Entregas:**
- Empty states com CTAs especificos e sequenciais:
  - Sem time: "Crie seu primeiro time para comecar" (ja existe no HomeView — ok)
  - Time sem projetos: "Mapeie um repositorio para o time" com botao que abre
    o painel de adicionar projeto no Workspace
  - Projetos sem analise: "Analise seus repositorios com IA para dar contexto
    aos agentes" com botao direto
  - Analise feita, sem demandas: "Crie sua primeira demanda para gerar stories
    com base no contexto dos seus repositorios"
- Readiness indicator no header do Workspace:
  - "X projetos mapeados, Y com contexto IA — pronto para gerar stories"
  - "X projetos sem analise — analise antes de gerar stories"
- Cada empty state tem link de "saiba mais" que explica o conceito (demanda, story,
  sprint) em uma linha

**Criterio de done:** PM novo abre o CodeForge, segue os CTAs sequenciais e chega
ate a criacao da primeira demanda em menos de 10 minutos sem documentacao externa.

### 1.6 CRUD completo de demandas e stories

**Problema:** Demandas e stories nao sao editaveis apos criacao. Stories geradas
sao read-only.

**Entregas:**
- `DemandDetailView`: campos editaveis inline (titulo, objetivo, criterios)
  com botao "Salvar alteracoes"
- Stories: botao de editar abre modal com campos editaveis
- Stories: botoes de aprovar/rejeitar por story individual
  - Aprovada: entra no backlog para sprint planning
  - Rejeitada: some da lista (soft delete ou status `rejected`)
- Botao "Regenerar" por story individual ou "Regenerar todas"
- Deletar demanda (com confirmacao, cascata para stories nao aprovadas)

**Criterio de done:** PM gera stories, edita o titulo de uma, rejeita outra,
aprova as restantes. As aprovadas aparecem disponiveis no sprint planning.

### Checklist Fase 1

- [x] Workspace reestruturado: projetos e repos como nodes na arvore
- [x] `linked_repository_id` no TeamDocument + migration
- [x] Reconciliacao automatica de pastas no Workspace
- [x] Auto-criacao de pastas ao criar/editar projeto/repo
- [x] SettingsView simplificado (removido tabs Projeto/Repos)
- [x] DocumentsView reescrito com arvore unificada
- [x] DELETE route para team-documents
- [x] PUT/DELETE endpoints para GitHub App credentials
- [x] Auto-migration no startup para PostgreSQL
- [ ] GitHub App: simplificar wizard para botao simples (depende de criar o App)
- [x] Adicionar projeto com validacao de path/git/URL
- [x] Editar e deletar projeto (inline rename + inline delete confirmation)
- [x] Analise cria documento navegavel no Workspace (`_save_context_team_document`)
- [x] Editor full-width e qualidade Confluence (MDXEditor com admonitions, diff source, frontmatter, images)
- [x] Todas as views filtram por time ativo (ProductView, KanbanView, AgentMonitorView)
- [x] Empty states com CTAs guiados (ProductView 4 fases, KanbanView 3 fases, DocumentsView)
- [x] Demandas editaveis (inline title/objective/criteria + "Melhorar com IA" + save)
- [x] Stories editaveis (EditStoryModal com title/description/criteria/references/project/repos)
- [x] Stories aprova/rejeita individual (Aprovar → backlog, Rejeitar → rejected)
- [x] Delete demanda com confirmacao inline (cascade warning)
- [x] Delete story com confirmacao inline
- [x] Regenerar stories (botao muda para "Regenerar Stories" quando ja existem)
- [x] Story status badges coloridos com labels em portugues

---

## Fase 2 — IA Inline e Assistencia Contextual

**Objetivo:** A IA participa ativamente em cada superficie — melhorando textos,
sugerindo criterios, expandindo documentos — sem nunca ser uma pagina separada.

**Pre-requisito:** Fase 1 completa.

### 2.1 Assistente inline no editor de documentos

**Problema:** Pilar do produto diz "usuario seleciona trecho e pede melhore isso".
Nao existe.

**Entregas:**
- Toolbar contextual no MDXEditor: ao selecionar texto, aparece floating toolbar
  com acoes:
  - "Melhorar" — reescreve com mais clareza
  - "Expandir" — adiciona detalhes tecnicos
  - "Simplificar" — reduz complexidade
  - "Traduzir para ingles"
- Cada acao envia o trecho selecionado + contexto do documento + contexto do time
  para o LLM via endpoint dedicado
- Resposta aparece inline substituindo a selecao (com opcao de desfazer)
- API: `POST /api/ai/inline-assist` — recebe texto, acao, contexto do time,
  retorna texto melhorado (streaming)

**Criterio de done:** PM abre documento no Workspace, seleciona um paragrafo,
clica "Expandir", IA reescreve com detalhes tecnicos usando contexto do time.
PM aceita ou desfaz.

### 2.2 Melhorar demanda com IA

**Problema:** O botao "Estruturar com IA" no NewDemandModal funciona, mas a melhoria
de demandas existentes nao existe.

**Entregas:**
- `DemandDetailView`: botao "Melhorar com IA" ao lado do campo de objetivo
  - Melhora o texto usando contexto dos projetos vinculados
  - Preview lado a lado: original vs sugestao
  - PM aceita, rejeita ou edita a sugestao
- Sugestao automatica de criterios de aceitacao baseada no texto da demanda
- Resultado aparece inline, nao em modal separado

**Criterio de done:** PM abre demanda existente, clica "Melhorar", IA sugere
texto melhorado com criterios, PM aceita parcialmente.

### 2.3 Breakdown de tasks com contexto real

**Problema:** `run_breakdown` existe no backend mas a UI de breakdown e basica.
O agente de breakdown precisa usar context_doc + documentos do Workspace.

**Entregas:**
- `BreakdownModal` redesenhado:
  - Mostra quais documentos de contexto serao usados (lista com checkboxes)
  - PM pode incluir/excluir documentos do workspace manualmente
  - Breakdown gera tasks com referencias a arquivos reais do codebase
  - Cada task mostra: titulo, descricao, arquivos afetados, complexidade estimada
  - PM aprova/rejeita tasks individualmente antes de entrar no backlog
- Backend: `run_breakdown` recebe `workspace_context` completo (docs manuais +
  gerados) e referencia arquivos reais do repo

**Criterio de done:** PM clica "Gerar Tasks" numa story, vê o breakdown com
referencias a arquivos reais, aprova 3 de 5 tasks, as 3 entram no backlog.

### Checklist Fase 2

- [x] Assistente inline no editor (floating toolbar: selecao → Melhorar/Expandir/Simplificar/EN)
- [x] Melhorar demanda existente com IA (improveDemandMutation no DemandDetailView)
- [x] Sugestao de criterios de aceitacao (suggestCriteriaMutation no NewDemandModal)
- [x] Breakdown disparavel do DemandDetailView (botao "Gerar Tasks" por story)
- [x] Preview de contexto usado antes do breakdown (BreakdownModal com repos analisados/pendentes)
- [x] Aprovacao individual de tasks do breakdown (checkboxes, select/deselect all, rejeitas sao deletadas)
- [x] DELETE /api/tasks/{id} endpoint + deleteTask() frontend API function

---

## Fase 3 — Execucao Autonoma com Isolamento

**Objetivo:** Tasks podem ser executadas por agentes de IA em git worktrees isolados.
O resultado e codigo real em uma branch separada, pronto para review.

**Pre-requisito:** Fase 2 completa.

### 3.1 Git worktrees para execucao isolada

**Problema:** Agentes executam mas sem isolamento de branch. O pipeline backend
existe (spec → plan → code → QA) mas nao cria worktrees.

**Entregas:**
- `GitService` completo:
  - `create_worktree(project, branch_name)` — cria worktree a partir da branch
    base do projeto
  - `commit_changes(worktree_path, message)` — commita no worktree
  - `push_branch(worktree_path)` — push da branch
  - `cleanup_worktree(worktree_path)` — remove worktree apos uso
- Pipeline de execucao integrado:
  - Task recebe `worktree_path` e `branch_name` ao iniciar
  - Todas as tools (Read, Write, Edit, Bash) operam dentro do worktree
  - Path containment garante que agente nao sai do worktree
  - Ao concluir QA: commita e push automatico
- Cleanup automatico de worktrees de tasks canceladas/falhadas

**Criterio de done:** Task executada por agente cria worktree, escreve codigo,
commita, faz push. Branch existe no repo com commits reais. Worktree e limpo
apos conclusao.

### 3.2 Execucao de task com IA pela UI

**Problema:** Nenhum botao "Executar com IA" no kanban. O pipeline existe mas
nao tem trigger na UI.

**Entregas:**
- `TaskCard` no kanban: botao "Executar com IA" (icone de play + "IA") para
  tasks em status `pending`
- Ao clicar:
  - Task muda para `in_progress`
  - `assignee_type` muda para `ai`
  - Backend spawna o pipeline completo: spec → plan → code → QA → code_review
  - Frontend: task card mostra fase atual em tempo real (pill animada)
  - Se `human_review_required`: task para em `awaiting_review`
- `TaskDetailPanel`: mostra logs do agente em tempo real (via SSE/WebSocket)
- Botao "Cancelar execucao" enquanto agente esta rodando
- Botao "Retomar manualmente" se agente falhou — muda assignee para human

**Criterio de done:** PM clica "Executar com IA" numa task, ve a fase mudando
no card do kanban em tempo real (SPEC → PLANNING → CODING → QA), agente termina,
task aparece em CODE_REVIEW com branch e diff disponivel.

### 3.3 Code review na UI

**Problema:** Code review agent existe no backend mas nenhuma UI de review.

**Entregas:**
- `TaskDetailPanel` expandido para tasks em `code_review` ou `awaiting_review`:
  - Diff view: mostra git diff da branch do agente vs branch base
  - Resumo do agente: o que foi implementado, arquivos modificados
  - Review de IA: se code_review_agent rodou, mostra findings
  - Acoes: "Aprovar e Mergear", "Solicitar Correcoes", "Rejeitar"
  - Se "Solicitar Correcoes": campo de texto para feedback, agente retenta
- Link externo para PR no GitHub (se integracao configurada)

**Criterio de done:** Task executada por agente chega em AWAITING_REVIEW.
Dev abre o painel, ve o diff, le o resumo, aprova. Task vai para DONE.

### 3.4 Human-in-the-loop configuravel pela UI

**Problema:** Settings mostra toggles de human-in-the-loop mas sao read-only.

**Entregas:**
- `SettingsView` reorganizado por time e projeto:
  - Secao "Time": config global do time
  - Secao "Projeto": config por projeto (override do time)
- Toggles editaveis (nao mais read-only):
  - `human_review_required` — code review humano obrigatorio
  - `breakdown_requires_approval` — tasks geradas precisam de aprovacao
  - `auto_start_tasks` — agentes comecam automaticamente apos sprint planning
  - `auto_merge` — merge automatico apos review (desabilitado por padrao)
- API: `PATCH /api/projects/{id}/config`, `PATCH /api/teams/{id}/config`

**Criterio de done:** Tech Lead vai em Settings, ativa `human_review_required`
para o projeto principal, desativa para o projeto de docs. Tasks do projeto
principal param em AWAITING_REVIEW, tasks do projeto de docs vao direto para DONE.

### Checklist Fase 3

- [ ] GitService cria/limpa worktrees
- [ ] Pipeline de execucao opera dentro do worktree
- [ ] Botao "Executar com IA" no kanban
- [ ] Fase atual visivel no card da task em tempo real
- [ ] Logs do agente visiveis no TaskDetailPanel
- [ ] Diff view para code review
- [ ] Aprovar/rejeitar/solicitar correcoes
- [ ] Human-in-the-loop configuravel na UI

---

## Fase 4 — Integracao GitHub e PR Real

**Objetivo:** O resultado do trabalho do agente e um Pull Request real no GitHub.
O status do PR atualiza o board automaticamente.

**Pre-requisito:** Fase 3 completa. GitHub App "KodeJutso" criado e configurado.

### 4.1 GitHub integration completa

**Nota:** O GitHub App ja esta implementado no backend (`github_app.py`) com
`build_app_jwt`, `get_repository_access` e `create_installation_token`. O que
falta e usar esses tokens para operacoes reais de git e PR.

**Entregas:**
- `GitHubGateway` implementado usando installation tokens do GitHub App:
  - `create_pull_request(repo, branch, title, body)` — cria PR via GitHub API
  - `get_pr_status(repo, pr_number)` — checks, review status
  - `merge_pr(repo, pr_number)` — merge (se auto_merge habilitado)
- Fluxo de PR automatico:
  - Agente conclui code review → sistema cria PR automaticamente
  - PR title/body gerados a partir da task + spec + resumo do agente
  - Link do PR salvo em `Task.pr_url`
  - Badge de PR no card do kanban
- Verificacao de acesso ao repo antes de executar task (via `get_repository_access`)
- Clone de repos via installation token (sem GITHUB_TOKEN manual)

### 4.2 Webhooks para status de PR

**Entregas:**
- Webhook receiver: `POST /api/webhooks/github`
- Eventos processados:
  - PR approved → task vai para DONE (se auto_merge desabilitado)
  - PR merged → task vai para DONE
  - PR changes requested → task volta para CODING com feedback
  - CI checks failed → alerta no monitor
- Status de CI visivel no TaskDetailPanel

### 4.3 Clone de repos remotos

**Entregas:**
- Ao adicionar projeto com URL (sem path local):
  - Backend clona repo usando installation token do GitHub App (sem GITHUB_TOKEN manual)
  - Path local preenchido automaticamente
  - Clone em diretorio configuravel (workspace root)
- Verificacao de acesso via GitHub App antes de clonar
- Pull automatico antes de criar worktree (repo sempre atualizado)

### Checklist Fase 4

- [ ] PR criado automaticamente apos agente concluir (usando GitHub App token)
- [ ] Link de PR no card do kanban
- [ ] Webhook atualiza status da task
- [ ] CI status visivel
- [ ] Clone de repos remotos via GitHub App (sem GITHUB_TOKEN manual)
- [ ] OAuth callback para detectar instalacao automaticamente (requer deploy)

---

## Fase 5 — Sprint Experience e Visibilidade

**Objetivo:** Sprint planning funcional, visao por entregavel no kanban, dashboard
com metricas reais.

**Pre-requisito:** Fase 3 completa (pode rodar em paralelo com Fase 4).

### 5.1 Sprint planning completo

**Entregas:**
- `SprintPlanningModal` redesenhado:
  - Selecionar stories aprovadas para a sprint
  - Ver tasks de cada story e complexidade estimada
  - Capacidade do time (configuravel) vs carga estimada
  - Atribuir tasks: humano, IA, ou nao atribuido
  - Iniciar sprint: muda status, tasks elegivas comecam execucao

### 5.2 Visao por entregavel no kanban

**Problema:** Apenas kanban classico por coluna. Product_scope pede visao por story.

**Entregas:**
- Toggle no Sprint Board: "Por Status" (kanban classico) / "Por Entregavel"
- Visao por entregavel:
  - Cada story e uma secao com suas tasks e progresso
  - Barra de progresso por story (tasks done / total)
  - Collapse/expand por story
- Visao classica: como esta hoje mas com filtro por story opcional

### 5.3 Dashboard com metricas reais

**Problema:** HomeView mostra contadores estaticos. Nao tem metricas de sprint,
atividade recente, ou alertas.

**Entregas:**
- Sprint ativa: progresso, dias restantes, burndown simplificado
- Atividade recente: ultimas tasks completadas/falhadas, ultimos PRs
- Alertas: tasks travadas (>2h em mesma fase), agentes falhados, review pendente
- Resumo gerado por IA (opcional): "3 tasks em code review, 1 agente travado ha 2h"
- Metricas de agentes: tasks por IA vs humano, taxa de sucesso, tokens gastos

### Checklist Fase 5

- [ ] Sprint planning funcional
- [ ] Visao por entregavel no kanban
- [ ] Dashboard com metricas de sprint
- [ ] Atividade recente
- [ ] Alertas de tasks travadas

---

## Fase 6 — Monitor de Agentes e Observabilidade

**Objetivo:** Visibilidade completa do que os agentes estao fazendo, com capacidade
de intervir.

### 6.1 Monitor de agentes em tempo real

**Entregas:**
- `AgentMonitorView` redesenhado:
  - Sessoes ativas com status ao vivo (SSE)
  - Logs de cada sessao em streaming (tipo terminal)
  - Uso de tokens por sessao com estimativa de custo
  - Botoes: Pausar, Cancelar, Retomar
- Historico de sessoes com filtros (por task, por tipo de agente, por resultado)
- Deteccao de loops: sistema identifica quando agente esta repetindo acoes
  (ex: QA falhando 3x no mesmo erro) e alerta

### 6.2 Metricas de custo

**Entregas:**
- Dashboard de custo: tokens gastos por sprint, por tipo de agente, por projeto
- Estimativa de custo por task antes de executar (baseada em complexidade)
- Alertas de custo: "Sprint atual ja consumiu X tokens, estimativa de Y para concluir"
- Configuracao de limites: maximo de tokens por task, por sprint

### Checklist Fase 6

- [ ] Logs em tempo real de agentes
- [ ] Pausar/cancelar/retomar agentes
- [ ] Deteccao de loops
- [ ] Dashboard de custo com estimativas
- [ ] Alertas e limites de tokens

---

## Fase 7 — Multi-usuario e Colaboracao

**Objetivo:** O CodeForge funciona para times reais, nao apenas um usuario solo.

### 7.1 Autenticacao e permissoes

**Entregas:**
- Sistema de auth (JWT ou session-based)
- Roles por time: PM, Tech Lead, Desenvolvedor
- Permissoes por role:
  - PM: criar/editar demandas, stories, sprint planning
  - Tech Lead: configurar projetos, human-in-the-loop, aprovar reviews
  - Dev: pegar tasks, executar com IA, fazer review
- Invite de membros por email

### 7.2 Notificacoes

**Entregas:**
- In-app: badge no sidebar com notificacoes nao lidas
- Eventos que geram notificacao:
  - Task em AWAITING_REVIEW (para reviewer)
  - Agente falhou (para quem iniciou)
  - Sprint terminando (para PM)
  - PR aprovado/rejeitado (para assignee)
- Opcional: webhook para Slack/Teams

### Checklist Fase 7

- [ ] Auth com JWT
- [ ] Roles e permissoes
- [ ] Invite de membros
- [ ] Notificacoes in-app
- [ ] Webhook para Slack (opcional)


## O que NAO esta neste roadmap

- **CLI (Typer + Rich):** Prioridade baixa. O produto e web-first. CLI e util
  para devs mas nao e o que desbloqueia valor de produto agora.
- **Cloud execution:** Execucao de agentes em VMs efemeras. Importante para escala
  mas prematuro antes de o fluxo local funcionar bem.
- **Mobile:** Web-only por enquanto.
- **Analytics de engenharia:** DORA metrics, produtividade. Fora do escopo do produto
  (ver product_scope.md secao 9).

---

## Dependencias entre fases

```
Fase 1 (Fundacao UX)
  ↓
Fase 2 (IA Inline)
  ↓
Fase 3 (Execucao Autonoma)  ──→  Fase 4 (GitHub + PR)
  ↓                                    ↓
Fase 5 (Sprint + Kanban)          Fase 4 (paralelo)
  ↓
Fase 6 (Monitor de Agentes)
  ↓
Fase 7 (Multi-usuario)
  ↓
Fase 8 (Jira)
```

Fases 4 e 5 podem rodar em paralelo apos a Fase 3.
Fase 6 depende da Fase 3 (precisa de agentes rodando para monitorar).
Fases 7 e 8 sao independentes entre si mas precisam da base estavel.

---

*Este roadmap e orientado por experiencia de produto, nao por completude tecnica.
Cada fase entrega valor perceptivel para o usuario. Backend sem UI nao conta como
entregue. Feature que o usuario nao descobre sozinho nao conta como existente.
O nome do produto e KodeJutso (nao CodeForge — CodeForge e o nome do pacote Python).*
