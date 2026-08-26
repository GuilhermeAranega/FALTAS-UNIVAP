"""
Armazenamento simples de estado persistente usando um Gist secreto do GitHub
como "banco de dados" — evita expor dados pessoais (presença, cache de
faltas) no histórico do repositório público, e não exige nenhum servidor.

Usa só a stdlib (urllib) pra não precisar adicionar dependências novas.
"""

import json
import urllib.error
import urllib.request

GIST_API = "https://api.github.com/gists/{}"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "faltas-univap-bot",
        "Content-Type": "application/json",
    }


def load(gist_id: str, token: str, filename: str = "cache.json") -> dict:
    req = urllib.request.Request(GIST_API.format(gist_id), headers=_headers(token))
    try:
        with urllib.request.urlopen(req) as resp:
            gist = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Falha ao ler o gist {gist_id}: HTTP {e.code} — {e.read().decode(errors='ignore')}") from e

    arquivo = gist.get("files", {}).get(filename)
    if not arquivo or not arquivo.get("content"):
        return {}
    return json.loads(arquivo["content"])


def save(gist_id: str, token: str, data: dict, filename: str = "cache.json") -> None:
    body = json.dumps({
        "files": {
            filename: {"content": json.dumps(data, ensure_ascii=False, indent=2)}
        }
    }).encode("utf-8")
    req = urllib.request.Request(GIST_API.format(gist_id), data=body, headers=_headers(token), method="PATCH")
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Falha ao salvar o gist {gist_id}: HTTP {e.code} — {e.read().decode(errors='ignore')}") from e
