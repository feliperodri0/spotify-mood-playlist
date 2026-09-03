"""
Contador de cota da YouTube Data API v3 — real, não estimado (ticket #2).

Antes deste ticket, nenhuma chamada real à API era contabilizada: o número
mostrado no produto ("custo estimado") sempre vinha de uma fórmula
(50 + 150*n), nunca do gasto acumulado de verdade no dia. Isso é arriscado
porque a cota (10.000 unidades/dia) é do projeto inteiro, compartilhada por
todo o grupo — qualquer pessoa pode zerá-la sem que as outras saibam.

Reseta à meia-noite no horário do Pacífico (America/Los_Angeles), o mesmo fuso
que o Google usa para resetar a cota de verdade — não meia-noite local.

Escopo: instrumenta o fluxo principal do produto (busca + criação de playlist
via `youtube_playlist_oauth.py`, chamado por `app_local/app.py`). Não
instrumenta `avaliacao/resolver_videos.py`, que é um script administrativo de
uso único (o próprio docstring dele diz "rode uma vez") — não é o risco de uso
repetido que este ticket existe para conter.

Persistência: um arquivo JSON local. Sem banco, sem concorrência real (servidor
Flask de desenvolvimento, um processo, grupo pequeno).
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ARQUIVO = Path(__file__).parent / "logs" / "cota_youtube.json"
LIMITE_DIARIO = 10_000
FUSO_RESET = ZoneInfo("America/Los_Angeles")

_lock = threading.Lock()


def _hoje_pacifico() -> str:
    return datetime.now(FUSO_RESET).date().isoformat()


def _carregar() -> dict:
    if not ARQUIVO.exists():
        return {"data": _hoje_pacifico(), "usadas": 0}
    dados = json.loads(ARQUIVO.read_text())
    if dados.get("data") != _hoje_pacifico():  # virou o dia (Pacífico): reseta
        return {"data": _hoje_pacifico(), "usadas": 0}
    return dados


def _salvar(dados: dict) -> None:
    ARQUIVO.parent.mkdir(exist_ok=True)
    ARQUIVO.write_text(json.dumps(dados))


def gastar(unidades: int) -> int:
    """Registra `unidades` gastas AGORA. Chamar no exato momento de cada
    chamada real à API que teve sucesso (search=100, videos.list=1,
    playlists.insert=50, playlistItems.insert=50) — nunca reconstruído depois
    por fora, a partir de contagens de sucesso/falha, porque isso reintroduz o
    mesmo tipo de estimativa que este módulo existe para substituir."""
    with _lock:
        dados = _carregar()
        dados["usadas"] += unidades
        _salvar(dados)
        return dados["usadas"]


def estado() -> dict:
    dados = _carregar()
    usadas = dados["usadas"]
    return {
        "usadas": usadas,
        "restantes": max(0, LIMITE_DIARIO - usadas),
        "limite": LIMITE_DIARIO,
        "reseta_em": "meia-noite, horário do Pacífico (America/Los_Angeles)",
    }
