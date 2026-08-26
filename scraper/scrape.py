"""
Scraper de faltas do Portal Aluno Online (UNIVAP).

Loga no portal, abre a página de Boletim (Notas e Faltas) e a página de
Horário de Aulas, e extrai as tabelas renderizadas (os grids são carregados
via AJAX proprietário do framework Techne/Lyceum, então lemos o DOM já
montado em vez de tentar replicar a chamada AJAX).

Credenciais vêm de variáveis de ambiente (nunca hardcoded):
  UNIVAP_USER
  UNIVAP_PASS

Saída: docs/data.json
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

BOLETIM_URL = "https://portal.univap.br/AOnline/AOnline/avaliacao/T032D.tp"
HORARIO_URL = "https://portal.univap.br/AOnline/AOnline/calendario/T007D.tp"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "data.json"
DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug"

# Regra padrão de frequência mínima no ensino superior brasileiro (75%).
# Ajuste aqui se sua instituição usar outro percentual.
FREQUENCIA_MINIMA = 0.75

# Colunas do grid de horário (T007D), na ordem Segunda -> Domingo.
DIAS_SEMANA = ["descHorario2", "descHorario3", "descHorario4", "descHorario5", "descHorario6", "descHorario7", "descHorario1"]


def login(page, usuario: str, senha: str) -> None:
    page.goto(BOLETIM_URL, wait_until="domcontentloaded")
    page.wait_for_selector("input[name='username']", timeout=30000)
    page.fill("input[name='username']", usuario)
    page.fill("input[name='password']", senha)

    # O botão de login nem sempre é uma tag <button> (framework legado do
    # portal), então usamos o name do campo submit em vez do type/tag.
    page.click("[name='sendCredentials']")
    page.wait_for_load_state("networkidle")

    if "login" in page.url.lower() or page.locator("input[name='password']").count() > 0:
        raise RuntimeError("Login falhou — verifique usuário/senha (secrets UNIVAP_USER/UNIVAP_PASS).")


def extract_grid_by_col_classes(page, grid_selector: str) -> list[dict]:
    """Extrai um grid Ext.js lendo o nome real do campo pela classe CSS
    (ex: x-grid3-col-faltasAluno), o que também pega campos ocultos que não
    aparecem no layout padrão da tela."""
    return page.eval_on_selector_all(
        f"{grid_selector} .x-grid3-row",
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


def extract_boletim(page) -> list[dict]:
    page.goto(BOLETIM_URL, wait_until="domcontentloaded")
    page.wait_for_selector("#grdBoletim", timeout=30000)
    page.wait_for_timeout(3000)  # dá tempo pro AJAX popular o grid

    rows = extract_grid_by_col_classes(page, "#grdBoletim")
    if not rows:
        _save_debug(page, "boletim")
    return rows


def extract_horario(page) -> list[dict]:
    page.goto(HORARIO_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#grpHorarioAulas", timeout=30000)
    except Exception:
        _save_debug(page, "horario")
        return []
    page.wait_for_timeout(3000)

    rows = extract_grid_by_col_classes(page, "#grpHorarioAulas")
    if not rows:
        _save_debug(page, "horario")
    return rows


def _save_debug(page, nome: str) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(DEBUG_DIR / f"{nome}.png"), full_page=True)
    (DEBUG_DIR / f"{nome}.html").write_text(page.content(), encoding="utf-8")
    print(f"Aviso: extração de '{nome}' veio vazia — screenshot/HTML de debug salvos em debug/.", file=sys.stderr)


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def codigo_disciplina(nome_completo: str) -> str:
    """'A520145 - Algoritmos e Programação' -> 'A520145'"""
    return nome_completo.split(" - ")[0].strip().upper()


def build_aulas_por_dia(horario_rows: list[dict]) -> dict[str, dict]:
    """A partir do grid de horário (1 linha por período/horário, 1 coluna por
    dia da semana), conta quantas aulas por dia cada disciplina tem.
    Retorna: { codigo_disciplina: {"aulas_por_semana": int, "dias_letivos": int} }
    """
    contagem: dict[str, dict[str, int]] = {}  # codigo -> {dia: count}

    for row in horario_rows:
        for dia_col in DIAS_SEMANA:
            texto = row.get(dia_col, "")
            if not texto:
                continue
            # A célula normalmente traz o código da disciplina na primeira linha/token.
            m = re.search(r"\b([A-Za-z]{1,3}\d{5,6})\b", texto)
            codigo = m.group(1).upper() if m else texto.strip().upper()
            if not codigo:
                continue
            contagem.setdefault(codigo, {}).setdefault(dia_col, 0)
            contagem[codigo][dia_col] += 1

    resultado = {}
    for codigo, dias in contagem.items():
        aulas_por_semana = sum(dias.values())
        dias_letivos = len(dias)
        resultado[codigo] = {
            "aulas_por_semana": aulas_por_semana,
            "dias_letivos": dias_letivos,
            "aulas_por_dia_medio": round(aulas_por_semana / dias_letivos, 2) if dias_letivos else None,
        }
    return resultado


def build_summary(raw_rows: list[dict], horario_por_codigo: dict[str, dict]) -> list[dict]:
    """Mapeia os campos do grid do Boletim (Techne/Lyceum) pro nosso formato:
    disciplina, faltas, aulas_previstas, percentual_faltas, pode_faltar_ainda
    (em aulas) e pode_faltar_dias (convertido usando a grade de horário)."""
    summary = []
    for row in raw_rows:
        disciplina = row.get("disciplinas")
        if not disciplina:
            continue

        faltas = parse_number(row.get("faltasAluno"))
        aulas = parse_number(row.get("aulasPrevistas"))
        situacao = row.get("situacaoMatricula")
        perc_presenca = parse_number(row.get("percPresenca"))

        # Calculamos direto de faltas/aulas (mais confiável); percPresenca é
        # só fallback, pois o portal retorna 0 nele quando a disciplina ainda
        # não teve aulas dadas — o que faria parecer 100% de faltas por engano.
        if faltas is not None and aulas:
            percentual_faltas = faltas / aulas
        elif perc_presenca is not None:
            percentual_faltas = 1 - (perc_presenca / 100)
        else:
            percentual_faltas = None

        pode_faltar_ainda = None
        if aulas is not None and faltas is not None:
            limite_faltas = aulas * (1 - FREQUENCIA_MINIMA)
            pode_faltar_ainda = max(0, round(limite_faltas - faltas, 1))

        horario_info = horario_por_codigo.get(codigo_disciplina(disciplina))
        pode_faltar_dias = None
        aulas_por_dia_medio = horario_info.get("aulas_por_dia_medio") if horario_info else None
        if pode_faltar_ainda is not None and aulas_por_dia_medio:
            pode_faltar_dias = int(pode_faltar_ainda // aulas_por_dia_medio)

        summary.append({
            "disciplina": disciplina,
            "situacao": situacao,
            "faltas": faltas,
            "aulas_previstas": aulas,
            "percentual_faltas": round(percentual_faltas * 100, 1) if percentual_faltas is not None else None,
            "pode_faltar_ainda": pode_faltar_ainda,
            "aulas_por_dia_medio": aulas_por_dia_medio,
            "pode_faltar_dias": pode_faltar_dias,
        })
    return summary


def main() -> int:
    usuario = os.environ.get("UNIVAP_USER")
    senha = os.environ.get("UNIVAP_PASS")
    if not usuario or not senha:
        print("Defina UNIVAP_USER e UNIVAP_PASS como variáveis de ambiente.", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            login(page, usuario, senha)
            raw_rows = extract_boletim(page)
            horario_rows = extract_horario(page)
        finally:
            browser.close()

    horario_por_codigo = build_aulas_por_dia(horario_rows)
    summary = build_summary(raw_rows, horario_por_codigo)

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
    print(f"OK — {len(summary)} disciplinas, {len(horario_por_codigo)} com horário mapeado, salvas em {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
