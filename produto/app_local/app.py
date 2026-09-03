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

import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

DIR = Path(__file__).parent          # produto/app_local/
PRODUTO = DIR.parent                 # produto/
PROJETO = PRODUTO.parent             # semana2Spotify/
ENTREGAS = PROJETO / "entregas"      # onde ficam os notebooks e os dados gerados por eles
sys.path.insert(0, str(PRODUTO))

from motor_playlist import MoodsContraditorios, PipelineMood  # noqa: E402
from youtube_playlist_oauth import (  # noqa: E402
    CotaEsgotada, autenticar, buscar_video_id, criar_playlist_youtube,
)
from googleapiclient.discovery import build  # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="")

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
    return send_from_directory(app.static_folder, "index.html")


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
        }
    )


if __name__ == "__main__":
    print("Abra http://localhost:5001 no navegador")
    app.run(host="127.0.0.1", port=5001, debug=False)
