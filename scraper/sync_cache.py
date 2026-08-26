"""
Roda logo depois do scrape.py (na mesma Action diária). Copia o resultado
recém-raspado (disciplinas, grade, atualizado_em) pro cache no Gist secreto,
preservando a lista de presenças manuais (check-ins) que já estiver lá —
o scraper não sabe nada sobre check-ins, só o Gist guarda os dois juntos.
"""

import json
import os
import sys
from pathlib import Path

import gist_store

DATA_PATH = Path(__file__).resolve().parent.parent / "docs" / "data.json"


def main() -> int:
    gist_id = os.environ.get("GIST_ID")
    gist_token = os.environ.get("GIST_TOKEN")
    if not gist_id or not gist_token:
        print("GIST_ID/GIST_TOKEN não configurados — pulando sincronização do cache.", file=sys.stderr)
        return 0

    scraped = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    cache = gist_store.load(gist_id, gist_token)
    cache["disciplinas"] = scraped.get("disciplinas", [])
    cache["grade"] = scraped.get("grade", [])
    cache["frequencia_minima"] = scraped.get("frequencia_minima")
    cache["atualizado_em"] = scraped.get("atualizado_em")
    cache.setdefault("presencas", [])
    cache.setdefault("faltas_manuais", [])

    gist_store.save(gist_id, gist_token, cache)

    # Reescreve docs/data.json incluindo presenças e faltas manuais já
    # registradas, pra elas aparecerem mesmo num deploy do cron diário.
    scraped["presencas"] = cache["presencas"]
    scraped["faltas_manuais"] = cache["faltas_manuais"]
    DATA_PATH.write_text(json.dumps(scraped, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Cache atualizado no gist ({len(cache['disciplinas'])} disciplinas, {len(cache['presencas'])} check-ins e {len(cache['faltas_manuais'])} faltas manuais preservados).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
