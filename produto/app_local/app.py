"""
Produto local — backend Flask
==============================

MVP local (roda só na sua máquina, não é publicado): serve a interface e
expõe endpoints, usando o motor único (`motor_playlist.py`) e o login OAuth
já autenticado em `../credenciais/token.json` (YouTube).

- POST /api/preview        → gera a playlist sequenciada (grátis, sem tocar a API do YouTube)
- POST /api/criar-youtube  → cria a playlist DE VERDADE no YouTube (gasta cota da API)

Rodar:
    cd entregas/produto_local
    ../../.venv/bin/python app.py
Depois abrir http://localhost:5001 no navegador.
"""

import os
import secrets
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session

DIR = Path(__file__).parent          # produto/app_local/
PRODUTO = DIR.parent                 # produto/
PROJETO = PRODUTO.parent             # semana2Spotify/
ENTREGAS = PROJETO / "entregas"      # onde ficam os notebooks e os dados gerados por eles
sys.path.insert(0, str(PRODUTO))

from motor_playlist import MoodsContraditorios, PipelineMood  # noqa: E402
from youtube_playlist_oauth import (  # noqa: E402
    CotaEsgotada, autenticar, buscar_video_id, criar_playlist_youtube,
)
import cota_youtube  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
import spotify_playlist as spotify  # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="")
# Sessão só guarda o token do Spotify do usuário. Chave efêmera: reiniciar o
# servidor desloga todo mundo, o que é o certo para um app local.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Carrega o pipeline uma única vez, na subida do servidor
pipeline = PipelineMood(ENTREGAS)
print("Catálogo carregado:", len(pipeline.df), "faixas")

# Limite de faixas por playlist, definido pela cota da YouTube Data API v3:
# cada faixa custa 100 unidades (search) + 50 (playlistItems.insert) = 150,
# mais 50 fixas para criar a playlist (playlists.insert) -> custo(n) = 50 + 150n.
# Cota padrão: 10.000 unidades/dia. TAMANHO_MAXIMO=30 -> 4.550 unidades (~45% da
# cota diária), deixando margem para gerar mais de uma playlist no mesmo dia.
# Justificativa completa em docs/decisoesEJustificativasInterface.md.
TAMANHO_MAXIMO = 30


def custo_cota(n: int) -> int:
    return 50 + 150 * n


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "landing.html")


@app.route("/api/vocabulario")
def vocabulario():
    return jsonify(
        {
            "moods": {
                palavra: {
                    "energy": float(pipeline.vocab_df.loc[palavra, "energy"]),
                    "valence": float(pipeline.vocab_df.loc[palavra, "valence"]),
                }
                for palavra in pipeline.vocabulario
            },
            # Quais palavras combinam com quais: o front desabilita as impossíveis
            # antes do clique, em vez de deixar o usuário errar e receber erro.
            "combinacoes": pipeline.combinacoes_possiveis(),
            "tamanho_maximo": TAMANHO_MAXIMO,
        }
    )


MINUTOS_MAXIMO = 180


def duracao_texto(ms):
    minutos = int(round(ms / 60000))
    return f"{minutos // 60}h{minutos % 60:02d}" if minutos >= 60 else f"{minutos} min"


@app.route("/api/cota")
def cota():
    return jsonify(cota_youtube.estado())


@app.route("/api/buscar-faixa")
def buscar_faixa():
    """Busca no catálogo inteiro (não nas candidatas de um clima) para escolher
    faixa inicial antes de gerar a playlist -- ticket #1."""
    consulta = request.args.get("q", "")
    return jsonify({"faixas": pipeline.buscar_faixas(consulta)})


CUSTO_MINIMO_PREVIEW = 500  # abaixo disso, recusa preview -- reserva cota pra criação de verdade


@app.route("/api/preview-video", methods=["POST"])
def preview_video():
    """Preview sob demanda de um resultado de busca, no YouTube (ticket #4).

    Existe porque nome+artista não bastam para confirmar que a semente
    escolhida é a faixa certa: 4.384 títulos do catálogo são ambíguos, e a API
    do Spotify não expõe mais preview de 30s (removido para apps criados
    depois de nov/2024 -- confirmado, o campo preview_url nem vem na resposta).

    Reaproveita buscar_video_id (blindagem por duração já existente) -- a
    contabilização de cota (search.list=100 + videos.list=1) já acontece
    dentro dela, instrumentada no ticket #2. Não gera cota extra aqui."""
    corpo = request.get_json(force=True)
    track_id = corpo.get("track_id", "")
    linhas = pipeline.df[pipeline.df["track_id"] == track_id]
    if linhas.empty:
        return jsonify({"erro": "Faixa não encontrada no catálogo."}), 404
    row = linhas.iloc[0]

    restantes = cota_youtube.estado()["restantes"]
    if restantes < CUSTO_MINIMO_PREVIEW:
        return jsonify({
            "erro": f"Restam só {restantes} unidades de cota hoje -- reservadas para criar playlists "
                    f"de verdade. Preview desabilitado até a cota resetar (meia-noite, horário do Pacífico)."
        }), 409

    try:
        creds = autenticar()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 500

    youtube = build("youtube", "v3", credentials=creds)
    try:
        video_id = buscar_video_id(youtube, row["track_name"], row["artists"], row["duration_ms"])
    except CotaEsgotada as e:
        return jsonify({"erro": f"A cota da API acabou durante a busca: {e}"}), 503

    if video_id is None:
        return jsonify({"erro": "Não encontrei essa faixa no YouTube.", "cota": cota_youtube.estado()}), 404
    return jsonify({"video_id": video_id, "cota": cota_youtube.estado()})


@app.route("/api/moods-compativeis")
def moods_compativeis():
    """Quais dos 8 moods combinam com a faixa escolhida como semente (ticket
    #3). Só olha as âncoras contra o vetor da faixa -- não gera candidatas."""
    track_id = request.args.get("track_id", "")
    return jsonify({"moods": pipeline.moods_compativeis(track_id, k=3)})


@app.route("/api/preview", methods=["POST"])
def preview():
    corpo = request.get_json(force=True)
    palavras = [p for p in corpo.get("palavras", []) if p in pipeline.vocabulario]
    modo = corpo.get("modo", "faixas")
    faixa_inicial = corpo.get("faixa_inicial") or None

    if not palavras:
        return jsonify({"erro": "Escolha pelo menos 1 mood válido."}), 400
    if len(palavras) > 3:
        return jsonify({"erro": "Máximo de 3 moods por vez."}), 400
    if modo not in ("faixas", "tempo"):
        return jsonify({"erro": "modo precisa ser 'faixas' ou 'tempo'."}), 400

    try:
        if modo == "tempo":
            minutos = int(corpo.get("minutos", 30))
            if not (5 <= minutos <= MINUTOS_MAXIMO):
                return jsonify({"erro": f"A duração precisa estar entre 5 e {MINUTOS_MAXIMO} minutos."}), 400
            playlist = pipeline.gerar_playlist_por_duracao(
                palavras, minutos=minutos, faixa_inicial=faixa_inicial, teto_faixas=TAMANHO_MAXIMO
            )
        else:
            n = int(corpo.get("n", 15))
            if not (1 <= n <= TAMANHO_MAXIMO):
                return jsonify({"erro": f"n precisa estar entre 1 e {TAMANHO_MAXIMO}."}), 400
            playlist = pipeline.gerar_playlist(palavras, n=n, faixa_inicial=faixa_inicial)
    except MoodsContraditorios as e:
        return jsonify({"erro": str(e)}), 400

    faixas = PipelineMood.playlist_para_registros(playlist)
    total_ms = int(playlist["duration_ms"].sum())
    return jsonify({
        "faixas": faixas,
        "custo_cota": custo_cota(len(faixas)),
        "duracao_total_ms": total_ms,
        "duracao_total": duracao_texto(total_ms),
        # Quando o alvo de tempo esbarra no teto de faixas (que existe por causa
        # da cota do YouTube), a playlist sai mais curta que o pedido — e o
        # usuário precisa saber por quê.
        "limitado_por_cota": modo == "tempo" and len(faixas) >= TAMANHO_MAXIMO,
        "faixa_inicial": faixas[0]["track_id"] if faixas else None,
    })


@app.route("/api/criar-youtube", methods=["POST"])
def criar_youtube():
    corpo = request.get_json(force=True)
    palavras = [p for p in corpo.get("palavras", []) if p in pipeline.vocabulario]
    track_ids = corpo.get("track_ids") or []
    privacidade = corpo.get("privacidade", "unlisted")

    if not palavras:
        return jsonify({"erro": "Escolha pelo menos 1 mood válido."}), 400
    if privacidade not in ("private", "unlisted", "public"):
        return jsonify({"erro": "privacidade inválida."}), 400
    if not (1 <= len(track_ids) <= TAMANHO_MAXIMO):
        return jsonify({"erro": f"Gere uma prévia primeiro (1 a {TAMANHO_MAXIMO} faixas)."}), 400

    restantes = cota_youtube.estado()["restantes"]
    estimativa = custo_cota(len(track_ids))
    if estimativa > restantes:
        return jsonify({
            "erro": f"Essa playlist custaria ~{estimativa} unidades de cota, mas só restam "
                    f"{restantes} hoje (reseta à meia-noite do Pacífico). Tente com menos faixas."
        }), 409

    # A prévia é o contrato: cria exatamente as faixas que o usuário aprovou, na
    # ordem que ele viu. Antes isto regerava a playlist do zero e só acertava
    # porque o motor era determinístico — com faixa inicial escolhida pelo
    # usuário, a prévia e a playlist criada divergiriam sem aviso.
    playlist = pipeline.faixas_por_id(track_ids)
    if len(playlist) != len(track_ids):
        return jsonify({"erro": "A prévia não bate com o catálogo. Gere a prévia de novo."}), 400

    try:
        creds = autenticar()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 500

    youtube = build("youtube", "v3", credentials=creds)

    video_ids, nao_encontradas = [], []
    titulo = f"[Protótipo] {' + '.join(palavras)}"
    descricao = "Playlist gerada automaticamente (mood por âncoras + sequenciamento por transição suave)."

    try:
        for _, row in playlist.iterrows():
            vid = buscar_video_id(youtube, row["track_name"], row["artists"], row.get("duration_ms"))
            video_ids.append(vid)
            if vid is None:
                nao_encontradas.append(f"{row['track_name']} — {row['artists']}")

        url, adicionadas, falhas_insercao = criar_playlist_youtube(
            youtube, titulo, descricao, video_ids, privacidade
        )
    except CotaEsgotada as e:
        return jsonify({
            "erro": f"A cota diária da API do YouTube acabou ({e}). Ela reseta à meia-noite no "
                    f"horário do Pacífico. Cada faixa custa 100 unidades para buscar e 50 para "
                    f"inserir, de 10.000 por dia — tente com menos faixas."
        }), 503

    return jsonify(
        {
            "url": url,
            "faixas": PipelineMood.playlist_para_registros(playlist),
            "nao_encontradas": nao_encontradas,
            # Números honestos: quantas faixas realmente entraram na playlist do
            # YouTube, não quantas foram geradas. Antes, o front mostrava as 30
            # geradas mesmo quando só 16 tinham entrado.
            "adicionadas": adicionadas,
            "total": len(video_ids),
            "falhas_insercao": len(falhas_insercao),
            "cota": cota_youtube.estado(),
        }
    )


# ---------------------------------------------------------------------------
# Spotify: os track_id do dataset SÃO os ids do Spotify, então não há busca —
# a faixa que o modelo escolheu é a que entra na playlist. Sem custo de busca,
# sem risco de cover/ao vivo, e uma playlist de 30 faixas cabe em 2 requisições.
# ---------------------------------------------------------------------------


@app.route("/api/spotify/status")
def spotify_status():
    if not spotify.configurado():
        return jsonify({"configurado": False, "logado": False})
    dados = session.get("spotify")
    if not dados:
        return jsonify({"configurado": True, "logado": False})
    try:
        token, atualizado = spotify.token_valido(dados)
        session["spotify"] = atualizado
        return jsonify({"configurado": True, "logado": True, **spotify.perfil(token)})
    except spotify.SpotifyErro as e:
        print(f"  [spotify status] token morto, forçando novo login: {e}", flush=True)
        session.pop("spotify", None)
        return jsonify({"configurado": True, "logado": False})


def _destino_pos_login():
    """Para onde voltar depois do login (?next=), restrito a um caminho local
    do próprio site -- nunca uma URL externa (evita open redirect). Sem `next`,
    mantém o comportamento de sempre: volta pra "/".

    Existe para o protótipo de redesign (prototipo_redesign.html) poder linkar
    /login/spotify?next=/prototipo_redesign.html%3Fvariant%3DB e voltar pra
    onde o login começou, em vez de sempre cair no produto real -- sem essa
    generalização, completar o login te tirava do protótipo no meio do fluxo."""
    bruto = request.args.get("next", "/")
    if not bruto.startswith("/") or bruto.startswith("//"):
        return "/"
    return bruto


@app.route("/login/spotify")
def spotify_login():
    # Clicar "Entrar" duas vezes (ou usar o botão voltar) sobrescrevia o state
    # da tentativa em andamento — quando essa completava, o valor não batia mais
    # e o callback recusava com "estado_invalido" mesmo com login correto.
    if "spotify_state" in session:
        return redirect("/spotify-processando")
    estado = secrets.token_urlsafe(16)
    session["spotify_state"] = estado
    session["spotify_next"] = _destino_pos_login()
    try:
        return redirect(spotify.url_autorizacao(estado))
    except spotify.SpotifyNaoConfigurado as e:
        session.pop("spotify_state", None)
        session.pop("spotify_next", None)
        return jsonify({"erro": str(e)}), 503


@app.route("/spotify-processando")
def spotify_processando():
    destino = session.get("spotify_next", "/")
    sep = "&" if "?" in destino else "?"
    return redirect(f"{destino}{sep}spotify=ja_em_andamento")


@app.route("/logout")
def logout():
    session.pop("spotify", None)
    return redirect(_destino_pos_login())


@app.route("/callback")
def spotify_callback():
    # A tentativa termina aqui de qualquer jeito: state consumido de uma vez,
    # sucesso ou falha, para nunca sobrar preso numa sessão para sempre.
    esperado = session.pop("spotify_state", None)
    destino = session.pop("spotify_next", "/")
    sep = "&" if "?" in destino else "?"

    if request.args.get("error"):
        print(f"  [spotify callback] usuário negou: {request.args.get('error')}", flush=True)
        return redirect(f"{destino}{sep}spotify=negado")
    if not request.args.get("state") or request.args["state"] != esperado:
        print("  [spotify callback] state não bate (login duplicado ou expirado)", flush=True)
        return redirect(f"{destino}{sep}spotify=estado_invalido")
    try:
        session["spotify"] = spotify.trocar_codigo(request.args["code"])
    except (spotify.SpotifyErro, spotify.SpotifyNaoConfigurado) as e:
        print(f"  [spotify callback] troca de código falhou: {e}", flush=True)
        return redirect(f"{destino}{sep}spotify=falhou")
    return redirect(f"{destino}{sep}spotify=ok")


@app.route("/api/criar-spotify", methods=["POST"])
def criar_spotify():
    corpo = request.get_json(force=True)
    palavras = [p for p in corpo.get("palavras", []) if p in pipeline.vocabulario]
    track_ids = corpo.get("track_ids") or []
    if not palavras or not track_ids:
        return jsonify({"erro": "Gere uma prévia primeiro."}), 400
    if not session.get("spotify"):
        return jsonify({"erro": "Entre com o Spotify primeiro."}), 401

    # O nome vem do campo que o usuário edita na tela (pré-preenchido com o
    # automático, mas o texto final é dele). Sem limite de tamanho documentado
    # pela API do Spotify -- os 100 caracteres aqui são só um teto de UX, não
    # uma regra da API.
    nome = (corpo.get("nome") or "").strip()[:100]
    if not nome:
        nome = f"soundpark · {' + '.join(palavras)}"

    try:
        token, atualizado = spotify.token_valido(session["spotify"])
        session["spotify"] = atualizado
        eu = spotify.perfil(token)

        indisponiveis = spotify.faixas_indisponiveis(token, track_ids)
        entram = [t for t in track_ids if t not in indisponiveis]
        if not entram:
            return jsonify({"erro": "Nenhuma das faixas está disponível na sua conta."}), 400

        playlist_id, url = spotify.criar_playlist(
            token, nome,
            "Gerada por mood (âncoras no espaço de audio features) e ordenada por transição suave.",
            publica=bool(corpo.get("publica")),
        )
        adicionadas = spotify.adicionar_faixas(token, playlist_id, entram)
    except spotify.SpotifyNaoConfigurado as e:
        return jsonify({"erro": str(e)}), 503
    except spotify.SpotifyErro as e:
        return jsonify({"erro": f"O Spotify recusou: {e}"}), 502

    return jsonify({
        "url": url, "adicionadas": adicionadas, "total": len(track_ids),
        "indisponiveis": len(indisponiveis),
    })


if __name__ == "__main__":
    print("Abra http://localhost:5001 no navegador")
    app.run(host="127.0.0.1", port=5001, debug=False)
