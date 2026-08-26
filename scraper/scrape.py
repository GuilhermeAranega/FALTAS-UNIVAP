"""
Scraper de faltas do Portal Aluno Online (UNIVAP).

Loga no portal, abre a página de Boletim (Notas e Faltas) e extrai a
tabela renderizada (o grid é carregado via AJAX proprietário do
framework Techne/Lyceum, então lemos o DOM já montado em vez de
tentar replicar a chamada AJAX).

Credenciais vêm de variáveis de ambiente (nunca hardcoded):
  UNIVAP_USER
  UNIVAP_PASS

Saída: docs/data.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL_URL = "https://portal.univap.br/AOnline/AOnline/avaliacao/T032D.tp"
LOGIN_URL = "https://portal.univap.br/AOnline/login"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "data.json"

# Regra padrão de frequência mínima no ensino superior brasileiro (75%).
# Ajuste aqui se sua instituição usar outro percentual.
FREQUENCIA_MINIMA = 0.75


def login(page, usuario: str, senha: str) -> None:
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    page.wait_for_selector("input[name='username']", timeout=30000)
    page.fill("input[name='username']", usuario)
    page.fill("input[name='password']", senha)

    # O botão de login nem sempre é uma tag <button> (framework legado do
    # portal), então usamos o name do campo submit em vez do type/tag.
    page.click("[name='sendCredentials']")
    page.wait_for_load_state("networkidle")

    if "login" in page.url.lower() or page.locator("input[name='password']").count() > 0:
        raise RuntimeError("Login falhou — verifique usuário/senha (secrets UNIVAP_USER/UNIVAP_PASS).")


def extract_grid(page) -> list[dict]:
    # O grid (id=grdBoletim) é um componente Ext.js; esperamos a tabela
    # interna renderizar e então lemos cabeçalho + linhas do DOM.
    page.wait_for_selector("#grdBoletim", timeout=30000)
    page.wait_for_timeout(3000)  # dá tempo pro AJAX popular o grid

    # As células do grid (Ext.js) trazem o nome do campo real na classe CSS
    # (ex: x-grid3-col-faltasAluno), independente do texto visível na coluna
    # — isso inclui campos ocultos como aulasPrevistas/percPresenca que não
    # aparecem no layout padrão da tela.
    rows = page.eval_on_selector_all(
        "#grdBoletim .x-grid3-row",
        """rows => rows.map(r => {
            const cells = r.querySelectorAll('.x-grid3-cell-inner');
            const record = {};
            cells.forEach(c => {
                const m = [...c.classList].map(cls => cls.match(/^x-grid3-col-(.+)$/)).find(Boolean);
                if (m) record[m[1]] = c.innerText.trim();
            });
            return record;
        }).filter(r => Object.keys(r).length > 0)""",
    )
    return rows


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def build_summary(raw_rows: list[dict]) -> list[dict]:
    """Mapeia os campos do grid do Boletim (Techne/Lyceum) pro nosso formato:
    disciplina, faltas, aulas_previstas, percentual_faltas, pode_faltar_ainda."""
    summary = []
    for row in raw_rows:
        disciplina = row.get("disciplinas")
        if not disciplina:
            continue

        faltas = parse_number(row.get("faltasAluno"))
        aulas = parse_number(row.get("aulasPrevistas"))
        situacao = row.get("situacaoMatricula")
        perc_presenca = parse_number(row.get("percPresenca"))

        # O portal já calcula percPresenca (% de presença); preferimos usar
        # esse valor oficial em vez de recalcular, e só caímos pro cálculo
        # manual (faltas/aulas) se ele não vier preenchido.
        if perc_presenca is not None:
            percentual_faltas = 1 - (perc_presenca / 100)
        else:
            percentual_faltas = (faltas / aulas) if (faltas is not None and aulas) else None
        pode_faltar_ainda = None
        if aulas is not None and faltas is not None:
            limite_faltas = aulas * (1 - FREQUENCIA_MINIMA)
            pode_faltar_ainda = max(0, round(limite_faltas - faltas, 1))

        summary.append({
            "disciplina": disciplina,
            "situacao": situacao,
            "faltas": faltas,
            "aulas_previstas": aulas,
            "percentual_faltas": round(percentual_faltas * 100, 1) if percentual_faltas is not None else None,
            "pode_faltar_ainda": pode_faltar_ainda,
        })
    return summary


def main() -> int:
    usuario = os.environ.get("UNIVAP_USER")
    senha = os.environ.get("UNIVAP_PASS")
    if not usuario or not senha:
        print("Defina UNIVAP_USER e UNIVAP_PASS como variáveis de ambiente.", file=sys.stderr)
        return 1

    debug_dir = Path(__file__).resolve().parent.parent / "debug"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login(page, usuario, senha)
            raw_rows = extract_grid(page)
            if not raw_rows:
                # Seletores do grid não bateram — salva screenshot + HTML
                # pra dar pra debugar sem precisar da senha do aluno.
                debug_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(debug_dir / "boletim.png"), full_page=True)
                (debug_dir / "boletim.html").write_text(page.content(), encoding="utf-8")
                print("Aviso: 0 disciplinas extraídas — screenshot/HTML de debug salvos em debug/.", file=sys.stderr)
        finally:
            browser.close()

    summary = build_summary(raw_rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
                "frequencia_minima": FREQUENCIA_MINIMA,
                "disciplinas": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"OK — {len(summary)} disciplinas salvas em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
