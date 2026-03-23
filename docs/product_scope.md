# CodeForge — Escopo de Produto

**Data:** 2026-03-22
**Versão:** 1.0

---

## 1. Visão do Produto

CodeForge é uma plataforma de gestão de produto e execução autônoma de código que unifica o trabalho de Product Managers, desenvolvedores e agentes de IA em um único ambiente operacional. O PM cria demandas, estrutura entregáveis e planeja sprints como faria no Jira — mas a IA participa ativamente em cada etapa: melhora textos, decompõe requisitos varrendo os repositórios reais, gera documentação de contexto e executa tarefas técnicas de forma autônoma dentro de git worktrees isolados. O resultado é um fluxo contínuo desde a ideia de produto até o Pull Request, onde humanos e agentes de IA colaboram no mesmo board e cada task pode ser executada por quem tiver mais capacidade naquele momento.

---

## 2. Personas

### Product Manager (PM)
Responsável por criar demandas, escrever entregáveis (stories), vincular projetos e planejar sprints. Não tem deep knowledge técnico sobre os repositórios. Precisa de ajuda da IA para escrever com precisão técnica e quer visibilidade do progresso sem precisar perguntar para um dev.

Dores atuais: escreve épicos vagos porque não conhece o codebase, precisa de reunião de refinamento para cada demanda, perde tempo em tasks administrativas de decomposição.

### Tech Lead / Desenvolvedor Sênior
Define arquitetura, revisa código, e toma decisões quando a IA trava. Pode pegar tasks manualmente ou deixar a IA executar e revisar apenas o resultado. Quer configurar o nível de autonomia da IA por projeto.

Dores atuais: gasta tempo em tarefas repetitivas de implementação, é gargalo para code review, precisa explicar contexto do codebase repetidamente.

### Desenvolvedor
Trabalha tasks do sprint no fluxo clássico (pega task, implementa, abre PR) ou delega para IA e revisa. Quer saber o que está acontecendo nas tasks dos agentes sem precisar abrir logs.

### Agente de IA
Não é uma persona humana, mas é um ator de primeira classe no sistema. Executa tasks autonomamente (spec → plan → código → QA), participa do code review, e pode ser spawn de outro agente para sub-tarefas. Precisa de contexto rico (documento do projeto, task bem descrita, branch isolada).

---

## 3. Pilares do Produto

### Pilar 1 — IA como Membro do Time, Não como Ferramenta
A IA não é um botão de "melhorar texto" em um canto da tela. Ela participa do processo de produto desde a criação da demanda até a aprovação do PR. Cada superfície do produto expõe assistência contextual: o PM recebe sugestões enquanto escreve um épico, a IA usa o contexto real dos repositórios para gerar stories técnicas precisas, e agentes executam tarefas completas autonomamente.

### Pilar 2 — Contexto é Infraestrutura
A IA é tão útil quanto o contexto que ela tem. O Workspace documental (equivalente ao Confluence) é a infraestrutura que alimenta todos os agentes. Documentos de análise de repositório, decisões de arquitetura, e documentos de produto não são arquivos mortos — são a memória operacional que torna os agentes mais precisos. Sem contexto, a IA é genérica. Com contexto, ela é um membro do time.

### Pilar 3 — Human-in-the-Loop Configurável
Autonomia não significa ausência de controle. Cada ponto do fluxo onde um humano pode querer intervir é configurável: aprovação de stories geradas pela IA, aprovação do breakdown de tasks antes de entrar no backlog, code review obrigatório por humano. O padrão é conservador (humano aprova tudo), mas times avançados podem abrir a autonomia progressivamente por projeto ou por demanda.

### Pilar 4 — Um Único Ambiente para PM e Dev
PMs e devs não deveriam trabalhar em ferramentas separadas que precisam de sincronização manual. O CodeForge é o sistema onde a demanda nasce, é decomposta, executada e entregue — sem exportar para Jira, sem copiar contexto para Slack, sem reunião de repasse entre o que está escrito no Confluence e o que está no board.

---

## 3.1 O Diferencial: Pipeline de Automação, Não Assistência de Texto

Todo produto de IA em 2026 "melhora texto". Isso é commodity. O CodeForge não é um assistente de escrita — é um **sistema de automação** que transforma uma ideia de produto em código pronto para review, usando o contexto real dos repositórios do time.

### A cadeia de valor

```
Repositório → Análise (executor IA) → Documento de Contexto
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

Cada elo desta cadeia depende da qualidade do anterior:

1. **Sem análise de repo** → stories genéricas, tasks vagas, execução falha.
2. **Com análise + docs do workspace** → stories referenciam módulos reais, tasks apontam para arquivos específicos, agente sabe exatamente onde e o que mudar.
3. **Com tudo acima + feedback do PM** (rejeitar story ruim, ajustar task) → sistema converge para output cada vez mais preciso.

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

O pipeline de automação é o diferencial, mas a IA deve estar presente em **toda superfície** onde fizer sentido. Melhorar texto de uma demanda, sugerir critérios de aceitação, expandir um documento, traduzir — tudo isso é parte natural do produto. Um PM que está escrevendo um épico e pode pedir "melhore isso" tem uma experiência melhor do que um que precisa copiar para um chat externo.

A distinção é de **prioridade, não de exclusão:**
- O investimento principal vai para a cadeia de automação (contexto → geração → execução)
- A assistência de texto entra naturalmente onde o usuário já está (editor, demanda, story) — é o Pilar 1 do produto ("IA como membro do time")
- A IA nunca vive numa página separada — sempre inline, contextual, acionável

---

## 4. Módulos Funcionais

### 4.1 Dashboard / Home

**O que faz:** Página inicial do time. Apresenta uma visão consolidada do estado atual: sprints ativas, demandas em andamento, tarefas de agentes rodando, alertas de tarefas travadas e atividade recente.

**User stories:**
- Como PM, quero ver de relance quantas tasks estão em andamento, quantas estão travadas e qual é o progresso da sprint atual, para não precisar abrir o kanban para ter essa visibilidade.
- Como desenvolvedor, quero ver as minhas tasks e as tasks dos agentes vinculadas às minhas demandas, para saber o que precisa da minha atenção hoje.
- Como Tech Lead, quero ver tarefas em `FAILED` ou `AWAITING_REVIEW` com destaque, para intervir rapidamente.

**Integração com IA:**
- Painel de resumo gerado por IA: "3 tarefas em code review aguardando sua aprovação, 1 agente travado há 2h na task X."
- Sugestão de próxima ação com base no estado da sprint.

---

### 4.2 Workspace (Base de Conhecimento)

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

### 4.3 Epics e Backlog de Produto

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

### 4.4 Sprint Board (Kanban)

**O que faz:** Gerenciamento de sprints e execução de tasks. O PM seleciona quais entregáveis entram na sprint. Tasks aparecem no kanban com duas visões: por entregável (visão de PM) e kanban clássico por coluna (visão de dev). Tasks podem ser atribuídas a humanos ou agentes de IA.

**Colunas do pipeline:**
```
BACKLOG → IN_PROGRESS → SPEC → PLANNING → CODING → QA → CODE_REVIEW → AWAITING_REVIEW → DONE
```
Estados terminais: `DONE`, `FAILED`, `CANCELLED`.

**User stories:**
- Como PM, quero planejar uma sprint selecionando entregáveis do backlog, para definir o escopo de trabalho de forma visual.
- Como desenvolvedor, quero ver no kanban todas as tasks da sprint com status em tempo real, incluindo as tasks executadas por agentes, para saber o que está acontecendo sem precisar perguntar.
- Como desenvolvedor, quero atribuir uma task a um agente de IA com um clique, para delegar trabalho repetitivo e focar em tarefas que precisam de julgamento humano.
- Como Tech Lead, quero configurar se code review por humano é obrigatório para um projeto específico, para ter controle granular sobre o que vai para produção sem aprovação.
- Como desenvolvedor, quero pegar uma task que o agente começou e continuar manualmente, para situações onde a IA travou e eu prefiro terminar direto.

**Integração com IA:**
- Execução autônoma de tasks: o agente passa por todas as fases do pipeline (spec → plan → código → QA → code review) sem intervenção humana, a não ser nos pontos de aprovação configurados.
- Agente de code review: mesmo em tasks executadas por humanos, a IA pode fazer o primeiro round de review, reduzindo o trabalho do Tech Lead.
- Detecção de bloqueios: a IA identifica quando uma task está em loop (ex: QA reprovando pela terceira vez no mesmo issue) e alerta o time para intervenção humana.

---

### 4.5 Gerenciamento de Projetos (Repositórios)

**O que faz:** Cadastro e gerenciamento de repositórios vinculados ao time. Dois fluxos de entrada: caminho local (para projetos na máquina do usuário) ou URL de repositório remoto. A IA analisa o repositório automaticamente após o cadastro e gera um documento de contexto. Projetos com contexto disponível aparecem com badge de status nas demandas.

**User stories:**
- Como Tech Lead, quero adicionar um repositório pelo caminho local ou URL, para que ele fique disponível para ser vinculado a demandas.
- Como Tech Lead, quero disparar a análise de um repositório e acompanhar o progresso em tempo real via streaming, para saber quando o documento de contexto estará pronto.
- Como PM, quero ver quais projetos já têm documento de contexto gerado ao vincular projetos a uma demanda, para saber se a IA terá informações suficientes para gerar stories precisas.
- Como Tech Lead, quero escolher qual executor de IA usar para analisar o repositório (Claude Code, Gemini CLI, etc.), para usar o executor mais adequado ao tamanho e complexidade do projeto.

**Integração com IA:**
- Análise via skills (`analyze-with-claude`, `analyze-with-gemini`, `analyze-with-opencode`): o skill executa o executor escolhido em modo subprocess, varre o repositório e gera um documento markdown estruturado com stack, estrutura, padrões, APIs, dependências externas e pontos de atenção.
- O documento de contexto gerado é salvo em `Project.context_doc` e também como documento navegável no Workspace do time.
- Reanalise: o usuário pode solicitar uma nova análise após mudanças significativas no projeto.

---

### 4.6 Orquestrador de Agentes

**O que faz:** Painel de monitoramento e controle dos agentes em execução. Mostra sessões ativas, logs em tempo real, uso de tokens, taxa de sucesso, e permite intervenções manuais (pausar, cancelar, retomar).

**User stories:**
- Como Tech Lead, quero ver todos os agentes rodando no momento com seu status, task associada e tempo de execução, para ter visibilidade do que está consumindo recursos.
- Como desenvolvedor, quero ver os logs de uma sessão de agente em tempo real, para entender o que ele está fazendo e intervir se necessário.
- Como Tech Lead, quero cancelar um agente que está em loop ou travado, para liberar recursos e realocar a task para um humano.
- Como Tech Lead, quero ver o histórico de sessões de agentes com taxa de sucesso por tipo de task, para calibrar quando faz sentido usar agentes e quando é mais eficiente delegar a humanos.

**Integração com IA:**
- Este módulo *monitora* agentes — não usa IA adicional para isso. A IA está nos agentes monitorados.
- Detecção automática de loops: o sistema identifica padrões repetitivos nos logs e sinaliza para intervenção humana.

**Métricas exibidas:**
- Sessões ativas e na fila
- Tokens consumidos (por sessão, por task, por sprint)
- Taxa de sucesso (tasks completadas / tasks iniciadas)
- Tempo médio por fase do pipeline

---

### 4.7 Configurações

**O que faz:** Configurações do time e do sistema. Inclui conexão com GitHub via GitHub App (fluxo simplificado — usuário só clica "Conectar" e autoriza repos), gerenciamento de chaves de API por provider de IA, seleção de modelo padrão, configurações de human-in-the-loop por projeto, e onboarding de novos membros do time.

**Seções:**
- **GitHub App**: Conexão com repositórios via GitHub App instalado pelo admin. Usuário clica "Conectar GitHub" e é redirecionado para autorizar repos — sem credentials manuais (fluxo idêntico ao Claude).
- **Providers de IA**: adicionar e testar chaves de API (Anthropic, OpenAI, Gemini, Ollama, etc.)
- **Modelos**: definir modelo padrão por tipo de agente (ex: Claude Sonnet para breakdown, Gemini para análise de repos grandes)
- **Human-in-the-loop**: configurações globais de aprovação — quando a IA precisa de aprovação humana
- **Time**: gerenciar membros, permissões
- **Executores**: verificar quais CLIs de IA estão disponíveis na máquina (Claude Code, Gemini CLI, OpenCode)
- **Workspace local**: pasta base para localizar repositórios na máquina

**User stories:**
- Como Tech Lead, quero configurar minha chave de API do Anthropic e testar a conexão, para verificar que os agentes vão funcionar antes de criar a primeira demanda.
- Como Tech Lead, quero definir que projetos críticos exigem code review humano obrigatório, para ter uma camada de segurança independente da autonomia configurada globalmente.
- Como PM, quero ver quais executores de IA estão disponíveis no meu ambiente, para saber quais opções de análise de repositório tenho disponíveis.

---

## 5. Fluxos Principais (User Journeys)

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

**Duração esperada:** 15–20 minutos para um usuário experiente com o repo já disponível localmente.

---

### Fluxo 2 — Épico até Execução Autônoma

```
1. PM escreve demanda (título + objetivo de negócio)
2. PM clica "Melhorar com IA" → demand_assistant sugere critérios de aceitação
3. PM vincula projetos ao épico (todos com contexto disponível)
4. PM clica "Gerar Stories" → story_generator cria entregáveis técnicos via SSE
5. PM revisa e aprova cada story (ou edita antes de aprovar)
6. PM clica "Gerar Tasks" por story → breakdown_agent varre cada repositório vinculado
7. Breakdown mostra tasks com referências a arquivos reais (ex: "Modificar PaymentService.py linha 45")
8. PM (ou Tech Lead) aprova o breakdown → tasks entram no backlog
9. Sprint planning: PM seleciona entregáveis para a sprint
10. Dev (ou PM) clica "Executar com IA" em tasks elegíveis
11. Agente inicia: SPEC → PLANNING → CODING → QA → CODE_REVIEW
12. Se human_review_required=true: task fica em AWAITING_REVIEW
13. Dev revisa o PR, aprova → task vai para DONE
```

---

### Fluxo 3 — Análise de Repositório

```
1. Usuário adiciona projeto (caminho local ou URL remota)
2. Sistema verifica quais skills de análise estão disponíveis (Claude Code, Gemini CLI, OpenCode)
3. Usuário seleciona executor e clica "Analisar"
4. Backend spawna subprocess com o executor escolhido
5. Logs fluem em tempo real via SSE para o frontend (SettingsView ou área de projetos)
6. Ao concluir: context_doc salvo no banco (Project.context_doc)
7. Documento markdown também salvo no Workspace do time
8. Badge do projeto muda de "Sem contexto" para "Contexto disponível"
9. Próximo épico vinculado a este projeto terá acesso ao contexto
```

---

### Fluxo 4 — Colaboração em Documento no Workspace

```
1. Tech Lead cria pasta "Arquitetura" no Workspace do time
2. Clica "Novo Documento" → abre editor em tela cheia (estilo Notion)
3. Escreve rascunho de ADR (Architecture Decision Record)
4. Seleciona um parágrafo e usa ação inline "Melhorar com IA"
5. IA expande o contexto usando documentos do Workspace como referência
6. Tech Lead revisa, aceita ou rejeita as sugestões
7. Salva documento → disponível imediatamente como contexto para todos os agentes do time
```

---

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

## 6. Princípios de UX

### Sem pastas auto-geradas
O sistema nunca cria estrutura de pastas automaticamente ao criar um time. Criar uma pasta vazia para "Arquitetura" que fica lá sem uso não agrega valor e cria ruído visual. O usuário começa com uma área limpa e cria a estrutura que faz sentido para ele.

### Editor em tela cheia
Qualquer documento no Workspace abre em modo de edição que ocupa toda a área disponível, sem sidebar ou painéis competindo por espaço. O foco é o conteúdo. Ações secundárias (salvar, exportar, pedir ajuda da IA) ficam em menus colapsáveis ou atalhos de teclado.

### IA como assistente inline, não como página separada
O usuário não "vai para a IA". A IA vem até onde o usuário está. No editor de demandas: botão "Melhorar" ao lado do campo. No breakdown: "Gerar tasks" por entregável. No kanban: "Executar com IA" no card. Nunca um modal separado de "chat com IA" que quebra o fluxo de trabalho.

### Streaming primeiro
Toda operação de IA que leva mais de 2 segundos deve mostrar progresso em tempo real. A espera silenciosa é a pior UX possível em um produto com IA. Logs fluindo, texto aparecendo palavra a palavra, barra de progresso — qualquer feedback é melhor que uma tela congelada.

### Progressive disclosure
Usuários novos não veem todas as configurações de human-in-the-loop, seleção de modelo por agente, configurações avançadas de pipeline. As defaults são conservadoras e funcionam. Configurações avançadas ficam em seções colapsáveis ou telas secundárias, acessíveis quando o usuário precisar.

### Aprovação explícita antes de execução
A IA nunca executa código ou commita sem aprovação explícita. Stories geradas ficam em estado "Proposta" até o PM aprovar. O breakdown de tasks fica em "Aguardando Aprovação" até o Tech Lead revisar. O usuário nunca acorda com um PR aberto que ele não autorizou.

---

## 7. Integrações Externas (Futuro — Fora do Foco Atual)

Integrações com ferramentas externas só fazem sentido quando o core funciona bem. Um canivete que não corta não precisa de saca-rolhas.

**Pré-requisito para qualquer integração:** O pipeline completo (demanda → stories → tasks → execução → código em branch) funciona end-to-end dentro do CodeForge sem depender de nenhuma ferramenta externa.

### Quando considerar (não agora):
- **GitHub/GitLab:** Criar PR automaticamente, webhooks de status, importar issues. Só faz sentido quando o agente já produz código em branches.
- **Jira:** Importar épicos existentes, sync bidirecional. Só faz sentido quando times com Jira legado querem migrar.
- **Slack/Teams:** Notificações de tasks travadas, resumo de sprint. Só faz sentido quando há sprint real com agentes rodando.
- **CI/CD:** Ler status de pipeline para informar o board. Só faz sentido quando há PRs reais sendo mergeados.

---

## 8. Métricas de Sucesso

### Métricas de produto (o que o CodeForge mede internamente)

| Métrica | Descrição |
|---------|-----------|
| Taxa de aprovação de stories geradas por IA | % de stories geradas que foram aprovadas sem edição significativa |
| Taxa de aprovação de breakdowns gerados por IA | % de tasks do breakdown aprovadas sem edição |
| Taxa de sucesso de execução autônoma | % de tasks executadas por agentes que chegaram a DONE sem intervenção humana |
| Tempo médio por fase do pipeline | Quanto tempo cada agente passa em cada fase (SPEC, PLANNING, CODING, QA) |
| Tokens por task | Custo de IA por task concluída, segmentado por tipo de agente |
| Retrabalho pós code review | % de tasks que voltaram de CODE_REVIEW para CODING mais de uma vez |

### Métricas de adoção (o que indica que o produto está funcionando)

| Métrica | Sinal positivo |
|---------|---------------|
| % de tasks com agente em sprints ativas | Time confia na IA para executar |
| Número de documentos criados no Workspace | Times estão usando como Confluence real |
| Tempo entre criação da demanda e primeiro PR | Velocidade do ciclo completo |
| NPS do PM após 30 dias | Produto entrega valor percebido para quem cria as demandas |

---

## 9. O Que NÃO É o CodeForge

**Não é um substituto para Claude Code, Aider ou Cursor.** O CodeForge orquestra esses executores, não compete com eles. O executor é o que escreve o código. O CodeForge decide *o que* executar, *quando*, em *qual repositório*, e *com qual contexto*.

**Não gerencia infraestrutura ou deploy.** O CodeForge abre PRs. O que acontece depois do merge é responsabilidade da pipeline de deploy da empresa. Nenhuma feature de CI/CD, container management ou deploy automation está no escopo.

**Não é uma ferramenta de chat.** Não há uma interface de chat livre com IA. Toda interação com IA é contextual e acionável: melhorar um texto, gerar stories, executar uma task. Sessões abertas de "pergunte qualquer coisa" não fazem parte do produto.

**Não é um IDE.** O editor do Workspace é para documentação, não para código. O CodeForge não tem um editor de código embutido. Código é editado pelo executor de IA no repositório local.

**Não é uma ferramenta de analytics de engenharia.** Métricas de DORA (deployment frequency, lead time, MTTR) e análise de produtividade de desenvolvedor não estão no escopo. O CodeForge mostra o progresso da sprint e o custo dos agentes — não um dashboard de engenharia.

**Não substitui o code review humano em projetos críticos.** O code review de IA é um primeiro filtro, não a palavra final. Times que precisam de rastreabilidade de aprovações e compliance devem usar `human_review_required=true`.

---

## 10. Roadmap de Alto Nível

O roadmap detalhado com checklists está em `docs/roadmap.md`. Aqui a visão de fases:

### Foco atual — Fazer o canivete cortar

O CodeForge tem motor backend robusto (pipelines, tools, AI provider, 403+ testes) e frontend com 7 views. Mas a experiência está quebrada e o pipeline de automação não está conectado end-to-end na UI. **Nenhuma integração externa faz sentido até o core funcionar bem.**

### Fase 1 — Fundação UX
Corrigir a experiência base: validação de projetos, editor full-width, filtros por time, onboarding guiado, CRUD completo de demandas/stories. O PM consegue usar o produto sem adivinhar.

### Fase 2 — Pipeline de Geração
Tornar a geração de stories e tasks **precisa, não genérica**. Stories referenciam módulos reais. Tasks apontam para arquivos específicos. O PM vê qual contexto alimentou a geração. Aprova, rejeita e ajusta artefatos individualmente. É aqui que o produto se diferencia de qualquer "chat com IA".

### Fase 3 — Pipeline de Execução
Agentes executam tasks em git worktrees isolados. Botão "Executar com IA" no kanban. Pipeline completo (spec → plan → code → QA → review) visível em tempo real. Resultado: código real em branch separada, pronto para review humano.

### Fase 4 — Visibilidade e Controle
Sprint planning funcional. Monitor de agentes em tempo real. Métricas de custo e sucesso. Human-in-the-loop configurável na UI. Dashboard com alertas de tasks travadas.

### Futuro — Só quando o core estiver afiado
Multi-usuário, GitHub/Jira/Slack, cloud execution. Nada disso entra no roadmap ativo até que o pipeline completo (demanda → código em branch) funcione end-to-end para um usuário solo.

---

*Este documento é o referencial de produto para o CodeForge. Decisões de desenvolvimento devem ser avaliadas contra os pilares, personas e princípios de UX descritos aqui — especialmente a seção 3.1 (Pipeline de Automação). Quando uma feature proposta não se encaixar em nenhum módulo descrito ou contradizer o que o produto não é, é um sinal para questionar antes de implementar.*
