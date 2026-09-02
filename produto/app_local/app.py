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

from motor_playlist import PipelineMood  # noqa: E402
from youtube_playlist_oauth import autenticar, buscar_video_id, criar_playlist_youtube  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="")

# Carrega o pipeline uma única vez, na subida do servidor
pipeline = PipelineMood(ENTREGAS)
print("Catálogo carregado:", len(pipeline.df), "faixas")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/vocabulario")
def vocabulario():
    return jsonify(
        {
            palavra: {
                "energy": float(pipeline.vocab_df.loc[palavra, "energy"]),
                "valence": float(pipeline.vocab_df.loc[palavra, "valence"]),
            }
            for palavra in pipeline.vocabulario
        }
    )


@app.route("/api/preview", methods=["POST"])
def preview():
    corpo = request.get_json(force=True)
    palavras = [p for p in corpo.get("palavras", []) if p in pipeline.vocabulario]
    n = int(corpo.get("n", 20))

    if not palavras:
        return jsonify({"erro": "Escolha pelo menos 1 mood válido."}), 400
    if len(palavras) > 3:
        return jsonify({"erro": "Máximo de 3 moods por vez."}), 400
    if not (1 <= n <= 50):
        return jsonify({"erro": "n precisa estar entre 1 e 50."}), 400

    playlist = pipeline.gerar_playlist(palavras, n=n)
    return jsonify({"faixas": PipelineMood.playlist_para_registros(playlist)})


@app.route("/api/criar-youtube", methods=["POST"])
def criar_youtube():
    corpo = request.get_json(force=True)
    palavras = [p for p in corpo.get("palavras", []) if p in pipeline.vocabulario]
    n = int(corpo.get("n", 20))
    privacidade = corpo.get("privacidade", "unlisted")

    if not palavras:
        return jsonify({"erro": "Escolha pelo menos 1 mood válido."}), 400
    if privacidade not in ("private", "unlisted", "public"):
        return jsonify({"erro": "privacidade inválida."}), 400

    playlist = pipeline.gerar_playlist(palavras, n=n)

    try:
        creds = autenticar()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 500

    youtube = build("youtube", "v3", credentials=creds)

    video_ids, nao_encontradas = [], []
    for _, row in playlist.iterrows():
        vid = buscar_video_id(youtube, row["track_name"], row["artists"])
        video_ids.append(vid)
        if vid is None:
            nao_encontradas.append(f"{row['track_name']} — {row['artists']}")

    titulo = f"[Protótipo] {' + '.join(palavras)}"
    descricao = "Playlist gerada automaticamente (clustering de mood + sequenciamento por transição suave)."
    url = criar_playlist_youtube(youtube, titulo, descricao, video_ids, privacidade)

    return jsonify(
        {
            "url": url,
            "faixas": PipelineMood.playlist_para_registros(playlist),
            "nao_encontradas": nao_encontradas,
        }
    )


if __name__ == "__main__":
    print("Abra http://localhost:5001 no navegador")
    app.run(host="127.0.0.1", port=5001, debug=False)
