"""
Criação de playlist no Spotify
==============================

Por que o Spotify é mais simples que o YouTube aqui: os `track_id` do dataset
**são** os ids do Spotify (base62 de 22 caracteres, verificado nas 113.549
linhas). Então não existe busca — a faixa que o modelo escolheu é a faixa que
entra na playlist, por id. Isso elimina de uma vez o custo de busca (100 unidades
por faixa no YouTube), o risco de entrar cover/ao vivo/reação no lugar da faixa
medida, e o teto de cota diária.

Uma playlist de 30 faixas custa 2 requisições (criar + adicionar até 100 URIs de
uma vez), contra 31 no YouTube.

Configuração (uma vez):

1. https://developer.spotify.com/dashboard -> Create app
2. Redirect URI: http://127.0.0.1:5001/callback
   (o Spotify exige HTTPS, com exceção de loopback IPv4 explícito — 127.0.0.1,
   não "localhost")
3. Guarde as chaves em produto/credenciais/spotify.json:
       {"client_id": "...", "client_secret": "...",
        "redirect_uri": "http://127.0.0.1:5001/callback"}
   A pasta credenciais/ é gitignored.
4. Settings -> User Management: adicione o e-mail de cada pessoa do grupo. Em
   modo de desenvolvimento o app atende até 25 contas.

Criar playlist NÃO exige Premium (Premium é exigido para reproduzir dentro do
navegador, pelo Web Playback SDK, que este projeto não usa).
"""

import base64
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

CREDENCIAIS = Path(__file__).parent / "credenciais" / "spotify.json"
AUTORIZAR = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
ESCOPOS = "playlist-modify-private playlist-modify-public"
LOTE = 100  # máximo de URIs por chamada de adição


class SpotifyNaoConfigurado(Exception):
    pass


class SpotifyErro(Exception):
    pass


def credenciais():
    if not CREDENCIAIS.exists():
        raise SpotifyNaoConfigurado(
            f"Crie {CREDENCIAIS} com client_id, client_secret e redirect_uri. "
            "Passos no topo de produto/spotify_playlist.py."
        )
    dados = json.loads(CREDENCIAIS.read_text())
    faltando = [c for c in ("client_id", "client_secret", "redirect_uri") if not dados.get(c)]
    if faltando:
        raise SpotifyNaoConfigurado(f"Faltam em {CREDENCIAIS.name}: {', '.join(faltando)}")
    return dados


def configurado():
    try:
        credenciais()
        return True
    except SpotifyNaoConfigurado:
        return False


def url_autorizacao(state):
    c = credenciais()
    return AUTORIZAR + "?" + urlencode({
        "client_id": c["client_id"], "response_type": "code",
        "redirect_uri": c["redirect_uri"], "scope": ESCOPOS, "state": state,
    })


def _post_token(dados):
    c = credenciais()
    basico = base64.b64encode(f"{c['client_id']}:{c['client_secret']}".encode()).decode()
    r = requests.post(TOKEN, data=dados, headers={"Authorization": f"Basic {basico}"}, timeout=15)
    if r.status_code != 200:
        raise SpotifyErro(f"token: {r.status_code} {r.text[:200]}")
    t = r.json()
    t["expira_em"] = time.time() + t.get("expires_in", 3600) - 60
    return t


def trocar_codigo(codigo):
    c = credenciais()
    return _post_token({
        "grant_type": "authorization_code", "code": codigo, "redirect_uri": c["redirect_uri"],
    })


def token_valido(sessao_token):
    """Renova se estiver perto de expirar. Devolve (access_token, token_atualizado)."""
    if sessao_token["expira_em"] > time.time():
        return sessao_token["access_token"], sessao_token
    novo = _post_token({"grant_type": "refresh_token", "refresh_token": sessao_token["refresh_token"]})
    novo.setdefault("refresh_token", sessao_token["refresh_token"])  # o Spotify nem sempre devolve outro
    return novo["access_token"], novo


def _get(token, caminho):
    r = requests.get(API + caminho, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    if r.status_code != 200:
        raise SpotifyErro(f"GET {caminho}: {r.status_code} {r.text[:200]}")
    return r.json()


def perfil(token):
    p = _get(token, "/me")
    return {"id": p["id"], "nome": p.get("display_name") or p["id"], "produto": p.get("product")}


def faixas_indisponiveis(token, track_ids, mercado=None):
    """Ids que o Spotify não devolve ou que não tocam no mercado do usuário.

    Vale conferir antes de criar: o dataset tem faixas que saíram do catálogo ou
    que não estão liberadas em todo país, e adicionar uma dessas cria uma linha
    morta na playlist.

    Um id por chamada, não em lote: "Get Several Tracks" (`/tracks?ids=...`)
    devolve 403 para este app mesmo com token limpo, sem usuário envolvido —
    medido diretamente contra a API, com client_credentials. "Get Track"
    (`/tracks/{id}`, um de cada vez) funciona normalmente. É a mesma família de
    restrição do `audio-features` que o projeto já documentava como cortado
    desde nov/2024 (planejamentoModelo.md) — o Spotify ampliou a lista de
    endpoints negados a apps em modo de desenvolvimento, e o lote entrou nela em
    algum momento depois disso. N requisições em vez de N/50 não pesa aqui: o
    teto de faixas por playlist já é 30."""
    ruins = []
    sufixo = f"?market={mercado}" if mercado else ""
    for track_id in track_ids:
        try:
            faixa = _get(token, f"/tracks/{track_id}{sufixo}")
        except SpotifyErro:
            ruins.append(track_id)
            continue
        if mercado and not faixa.get("is_playable", True):
            ruins.append(track_id)
    return ruins


def criar_playlist(token, nome, descricao, publica=False):
    """Cria a playlist do usuário autenticado.

    Migração de fevereiro/2026 do Spotify: `POST /users/{user_id}/playlists`
    (que exigia o id do usuário na URL) foi substituído por `POST /me/playlists`,
    sempre "o usuário do token". O endpoint antigo devolve 403 genérico
    ("Forbidden", sem motivo) para apps em Development Mode — foi a causa real
    de "criar playlist: 403" mesmo com o escopo certo no token, descoberta lendo
    o guia de migração do Spotify (não estava documentada na referência
    normal da API, só no tutorial de migração)."""
    r = requests.post(
        f"{API}/me/playlists",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"name": nome, "description": descricao, "public": publica},
        timeout=15,
    )
    if r.status_code not in (200, 201):
        # Um 403 aqui não diz o motivo no corpo ("Forbidden" e mais nada). O
        # cabeçalho WWW-Authenticate de respostas OAuth costuma carregar o
        # motivo real (ex.: error="insufficient_scope") quando o Spotify se
        # dá ao trabalho de mandar; nem sempre manda.
        motivo = r.headers.get("www-authenticate", "")
        print(f"  [spotify criar_playlist] {r.status_code} corpo={r.text[:200]!r} www-authenticate={motivo!r}", flush=True)
        raise SpotifyErro(f"criar playlist: {r.status_code} {r.text[:200]}" + (f" ({motivo})" if motivo else ""))
    p = r.json()
    return p["id"], p["external_urls"]["spotify"]


def adicionar_faixas(token, playlist_id, track_ids):
    """Adiciona em lotes de 100, na ordem recebida. Devolve quantas entraram.

    Mesma migração de fevereiro/2026: `/playlists/{id}/tracks` virou
    `/playlists/{id}/items`. O corpo (`{"uris": [...]}`) não muda pela
    documentação consultada, mas isso é o que o guia de migração afirmou — se o
    Spotify recusar por causa do corpo, o erro virá com detalhe (diferente do
    403 genérico da criação), então dá para ajustar rápido se acontecer."""
    adicionadas = 0
    for i in range(0, len(track_ids), LOTE):
        uris = [f"spotify:track:{t}" for t in track_ids[i:i + LOTE]]
        r = requests.post(
            f"{API}/playlists/{playlist_id}/items",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"uris": uris},
            timeout=20,
        )
        if r.status_code not in (200, 201):
            raise SpotifyErro(f"adicionar faixas: {r.status_code} {r.text[:200]}")
        adicionadas += len(uris)
    return adicionadas
