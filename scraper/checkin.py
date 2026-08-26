"""
Disparado via GitHub Actions `repository_dispatch` (evento "checkin"), que o
Atalho do iPhone chama quando você chega na faculdade. Registra a data de
hoje (horário de Brasília) como presença confirmada por você — independente
do que o professor tiver marcado (ou esquecido de marcar) no portal — e
reconstrói docs/data.json a partir do cache no Gist pra já publicar no
Pages com o novo check-in refletido, sem precisar esperar o cron do dia
seguinte nem rodar o Playwright de novo.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import gist_store

DATA_PATH = Path(__file__).resolve().parent.parent / "docs" / "data.json"
BRASILIA = timezone(timedelta(hours=-3))


def main() -> int:
    gist_id = os.environ.get("GIST_ID")
    gist_token = os.environ.get("GIST_TOKEN")
    if not gist_id or not gist_token:
        print("GIST_ID/GIST_TOKEN não configurados.", file=sys.stderr)
        return 1

    cache = gist_store.load(gist_id, gist_token)
    presencas = cache.setdefault("presencas", [])

    hoje = datetime.now(BRASILIA).date().isoformat()
    if hoje not in presencas:
        presencas.append(hoje)
        presencas.sort()
        gist_store.save(gist_id, gist_token, cache)
        print(f"Check-in registrado para {hoje}.")
    else:
        print(f"Já havia check-in para {hoje} — nada a fazer.")

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(
            {
                "atualizado_em": cache.get("atualizado_em"),
                "frequencia_minima": cache.get("frequencia_minima", 0.75),
                "disciplinas": cache.get("disciplinas", []),
                "grade": cache.get("grade", []),
                "presencas": presencas,
                "faltas_manuais": cache.get("faltas_manuais", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
