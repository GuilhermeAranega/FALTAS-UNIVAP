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
suas credenciais no fork de outra pessoa.

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
