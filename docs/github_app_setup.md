# KodeJutso — Setup do GitHub App

**Data:** 2026-03-23
**Status:** Pendente (admin precisa criar o App no GitHub)

---

## Contexto

O KodeJutso precisa de um GitHub App para acessar repositorios privados dos usuarios.
O fluxo desejado e identico ao do Claude (Anthropic):

1. Admin cria o GitHub App "KodeJutso" **uma unica vez**
2. Credenciais do App ficam no backend (`.env` do servidor)
3. Usuario final so ve um botao **"Conectar GitHub"** que redireciona para a pagina de instalacao do App
4. Usuario escolhe a org/conta, seleciona repos, clica "Install & Authorize"
5. Pronto — KodeJutso consegue acessar os repos autorizados

O usuario **nunca** lida com App ID, private key ou qualquer credencial.

---

## Parte 1 — O que o ADMIN precisa fazer (unica vez)

### 1.1 Criar o GitHub App

Acesse: **https://github.com/organizations/KodeJutso/settings/apps/new**

Se a org KodeJutso nao tiver permissao para criar Apps, use a conta pessoal:
`https://github.com/settings/apps/new`

### 1.2 Preencher os campos

| Campo | Valor |
|---|---|
| **GitHub App name** | `KodeJutso` |
| **Homepage URL** | `https://github.com/KodeJutso` (qualquer URL valida) |
| **Callback URL** | Deixar **em branco** (sem OAuth user flow por enquanto) |
| **Setup URL** | Deixar em branco |
| **Webhook** | **Desmarcar** "Active" (nao precisamos de webhook por enquanto) |
| **Webhook URL** | Deixar em branco |

### 1.3 Permissoes (Repository permissions)

| Permissao | Nivel |
|---|---|
| **Contents** | Read & write |
| **Metadata** | Read-only (ja vem marcado por padrao) |
| **Pull requests** | Read & write |
| **Issues** | Read & write |

Tudo o mais: **No access**.

**Organization permissions:** Tudo como esta (nenhuma).
**Account permissions:** Tudo como esta (nenhuma).

### 1.4 Onde pode ser instalado

Selecionar: **"Any account"**

Isso permite que qualquer usuario do GitHub instale o App na sua conta/org.

### 1.5 Clicar "Create GitHub App"

### 1.6 Anotar o App ID

Apos criar, a pagina do App mostra o **App ID** no topo (um numero, ex: `123456`).

O **slug** e o nome em minusculas/kebab-case na URL:
`https://github.com/apps/kodejutso` → slug = `kodejutso`

### 1.7 Gerar a Private Key

Na mesma pagina do App, rolar ate **"Private keys"** e clicar **"Generate a private key"**.

Um arquivo `.pem` sera baixado automaticamente. **Guardar em local seguro.**

### 1.8 Salvar as credenciais no .env do backend

Adicionar ao arquivo `codeforge/.env`:

```env
GITHUB_APP_ID=123456
GITHUB_APP_SLUG=kodejutso
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"
```

**Nota sobre a private key:** O conteudo do `.pem` tem quebras de linha reais.
No `.env`, substituir cada quebra de linha por `\n` (literal) e colocar o valor entre aspas,
OU colar o conteudo completo em uma unica linha com `\n` separando.

O backend ja trata a conversao de `\n` literal para quebras de linha reais
em `load_github_app_settings()`.

---

## Parte 2 — O que o CODIGO precisa fazer (trabalho do dev)

### 2.1 Backend (ja feito parcialmente)

**Ja existe:**
- `GET /api/settings/github-app` — retorna `{ configured, app_slug, install_url }`
- `PUT /api/settings/github-app` — salva credentials no .env (endpoint para admin, nao usuario)
- `DELETE /api/settings/github-app` — remove credentials
- `GET /api/settings/github-app/repository-access?repo_url=...` — verifica acesso a um repo
- `load_github_app_settings()` — le env vars e retorna `GitHubAppSettings`
- `build_app_jwt()` — gera JWT para autenticacao como App
- `get_repository_access()` — verifica se o App tem acesso a um repo
- `create_installation_token()` — gera token de instalacao para operacoes git

**O que falta:**
- Nenhum endpoint novo necessario para o fluxo basico
- Quando houver deploy com dominio publico: adicionar **OAuth user flow** com callback
  para que o KodeJutso saiba automaticamente quando o usuario instalou o App
  (hoje, detectamos via `get_repository_access` quando o usuario tenta usar um repo)

### 2.2 Frontend (precisa simplificar)

**Estado atual:** Wizard de 3 etapas onde o usuario preenche App ID, slug e private key.
Isso esta **errado** para o fluxo desejado. O usuario nao deve preencher nada disso.

**O que precisa mudar:**

A secao GitHub App no Settings deve ter **dois estados:**

**Estado 1 — App nao configurado (admin nao colocou credentials no .env):**
```
[icone warning]
Conexao com GitHub nao disponivel.
O administrador do sistema precisa configurar o GitHub App.
Consulte a documentacao de setup.
```

**Estado 2 — App configurado (credentials no .env):**
```
[icone GitHub]
Conectar com GitHub

Conecte sua conta GitHub para que o KodeJutso acesse
seus repositorios privados com permissoes granulares.

[Botao: Conectar GitHub]  →  abre github.com/apps/{slug}/installations/select_target

Status: Configurado | Slug: kodejutso
```

Se o App ja esta instalado e o usuario quer gerenciar repos:
```
[icone check verde]
GitHub conectado via KodeJutso App

Gerencie quais repositorios o KodeJutso pode acessar.

[Botao: Gerenciar repositorios]  →  abre github.com/apps/{slug}/installations/select_target
```

**Resumo das mudancas:**
1. Remover o wizard de 3 etapas com campos de App ID/slug/private key
2. Remover os campos de input — usuario nao preenche nada
3. Se `configured=false`: mostrar mensagem para admin
4. Se `configured=true`: mostrar botao "Conectar GitHub" que abre a URL de instalacao
5. Manter o endpoint PUT/DELETE para uso administrativo (nao exposto na UI padrao)

### 2.3 Futuro — OAuth callback (quando houver deploy)

Quando o KodeJutso tiver dominio publico, o fluxo ideal e:

1. Adicionar **Setup URL** no GitHub App: `https://app.kodejutso.com/api/github/callback`
2. Ao clicar "Conectar GitHub", o usuario e redirecionado para a instalacao
3. Apos instalar, GitHub redireciona de volta para a Setup URL com `installation_id`
4. Backend salva o `installation_id` vinculado ao usuario/time
5. Frontend mostra status "Conectado" sem precisar verificar repo por repo

Isso e uma melhoria de UX mas **nao e bloqueante**. O fluxo atual
(verificar acesso repo por repo via `get_repository_access`) funciona.

---

## Resumo de responsabilidades

| Quem | O que | Quando |
|---|---|---|
| **Admin (Carlos)** | Criar GitHub App no GitHub, salvar credentials no .env | Antes de usar o fluxo de repos privados |
| **Dev (codigo)** | Simplificar frontend para botao simples | Proxima sessao de dev |
| **Dev (codigo)** | OAuth callback com redirect | Quando houver deploy com dominio publico |

---

## Referencia: como o Claude faz

O Claude (Anthropic) tem um GitHub App chamado "Claude" (slug: `claude`).
Na UI do Claude, quando o usuario clica "Add content from GitHub", ele e
redirecionado para `github.com/apps/claude/installations/select_target`.
La, o usuario escolhe a org, seleciona os repos, e clica "Install & Authorize".
O GitHub redireciona de volta para `claude.ai/connect/github/callback`.
O Claude salva a instalacao e lista os repos disponiveis num dropdown.

O KodeJutso deve seguir esse mesmo padrao: App criado uma vez pelo admin,
usuario so clica um botao e autoriza. Zero configuracao manual de credentials.
