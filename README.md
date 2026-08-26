# Faltas UNIVAP

Dashboard automático de faltas do Portal Aluno Online (UNIVAP).

Este repositório é público e serve como **template**: qualquer aluno da UNIVAP pode
usar sua própria cópia (fork) com o próprio login, sem que os dados de faltas de
ninguém apareçam no código ou no histórico do git.

## Como funciona

1. Um GitHub Action roda todo dia (`.github/workflows/faltas.yml`), faz login no portal
   com Playwright e extrai a tabela de notas/faltas.
2. O resultado (`data.json`) é publicado **só como artifact do GitHub Pages** — ele
   nunca é commitado no repositório, então seus dados de frequência não ficam
   expostos no histórico do git, mesmo em repo público.
3. `docs/index.html` (servido via GitHub Pages) lê esse JSON e mostra um dashboard
   simples com % de faltas e quanto ainda dá pra faltar por matéria.

## Setup (uma vez só, por pessoa)

Cada aluno deve usar sua **própria cópia** (fork) do repositório — nunca compartilhe
suas credenciais no fork de outra pessoa. Secrets e variables do GitHub Actions
**não são copiados automaticamente** quando alguém dá fork, então cada pessoa
repete todo o setup abaixo (incluindo a seção de check-in) no próprio fork.

1. Dê **Fork** neste repositório (ou clone e suba pro seu próprio repo novo):
   ```bash
   git clone <URL_DO_SEU_FORK>
   ```

2. Em **Settings → Secrets and variables → Actions**, adicione:
   - `UNIVAP_USER` — sua matrícula/CPF/e-mail de login
   - `UNIVAP_PASS` — sua senha do portal

3. Em **Settings → Pages → Build and deployment → Source**, selecione **"GitHub Actions"**
   (não "Deploy from a branch" — o workflow já publica via artifact).

4. Rode o workflow manualmente uma vez em **Actions → Atualizar faltas → Run workflow**
   para gerar o primeiro dashboard sem esperar o cron do dia seguinte.

Seu dashboard fica em `https://<seu-usuario>.github.io/<repo>/`, visível só pra quem
tiver o link — os dados de faltas de ninguém ficam versionados no código.

## Check-in manual de presença (opcional)

Às vezes o professor esquece de marcar a frequência certinho no portal. Pra ter um
registro seu, independente da UNIVAP, dá pra configurar um Atalho no iPhone que
dispara um "cheguei na faculdade" sempre que você chega — sem servidor próprio,
usando só GitHub (Actions + um Gist secreto como armazenamento).

### 1. Criar o Gist secreto (cache)

Crie um Gist **secreto** (não público) em [gist.github.com](https://gist.github.com)
com um arquivo `cache.json` contendo apenas `{}`. Copie o ID do gist (a parte final
da URL, ex: `https://gist.github.com/seu-usuario/`**`a1b2c3d4e5f6`**).

### 2. Criar um token só pra escrever no Gist

Em [github.com/settings/tokens](https://github.com/settings/tokens) → "Generate new
token (classic)" → marque **apenas o escopo `gist`** → gere e copie o token.

### 3. Configurar no repositório

- **Settings → Secrets and variables → Actions → Variables**: adicione `GIST_ID` com o ID copiado no passo 1.
- **Settings → Secrets and variables → Actions → Secrets**: adicione `GIST_TOKEN` com o token do passo 2.

### 4. Criar um token separado só pra disparar o check-in

Esse token fica **só no seu iPhone** (nunca no GitHub) e precisa poder disparar
Actions neste repositório. Em
[github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
crie um **fine-grained token**, escopo só este repositório, permissões:
- Contents: **Read and write**
- Actions: **Read and write**

Copie o token gerado (só aparece uma vez).

### 5. Criar o Atalho no iPhone

No app **Atalhos**, crie um novo atalho (pode virar uma Automação por localização,
disparando ao chegar na faculdade):

1. Ação **"Obter conteúdo de URL"**
2. URL: `https://api.github.com/repos/<seu-usuario>/<seu-fork>/dispatches` (troque pelo
   seu próprio usuário/repositório — cada fork dispara só a própria Action)
3. Método: `POST`
4. Cabeçalhos:
   - `Authorization`: `Bearer SEU_TOKEN_DO_PASSO_4`
   - `Accept`: `application/vnd.github+json`
   - `Content-Type`: `application/json`
5. Corpo (JSON): `{"event_type": "checkin"}`

Ao disparar, a Action `checkin.yml` roda em segundos, registra o dia de hoje (fuso
de Brasília) e republica o dashboard com a seção "Presença confirmada por mim"
atualizada — sem depender do que o professor marcou no portal.

## Testar localmente

```bash
cd scraper
pip install -r requirements.txt
playwright install chromium
UNIVAP_USER=... UNIVAP_PASS=... python scrape.py
```

## Ajustar a regra de frequência mínima

Por padrão assume 75% (regra comum no ensino superior brasileiro). Se a UNIVAP usar
outro valor, mude `FREQUENCIA_MINIMA` em `scraper/scrape.py`.

## Nota sobre a extração dos dados

A tabela de notas/faltas do portal é carregada via um componente Ext.js/Techne
(chamada AJAX proprietária), não como HTML estático. Por isso o scraper usa um
navegador real (Playwright) e lê o grid já renderizado, em vez de tentar replicar
a chamada AJAX. Se a UNIVAP mudar o layout da página, pode ser necessário ajustar
os seletores em `extract_grid()`.
