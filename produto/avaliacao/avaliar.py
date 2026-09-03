"""
Servidor de avaliação — o único que pode ficar público.
=======================================================

Serve a tela de escuta cega e grava as respostas. Deliberadamente NÃO tem:

- o motor (`PipelineMood`): o par já está congelado em `par_avaliacao.json`;
- credenciais OAuth: não lê `token.json`;
- qualquer rota que escreva no YouTube ou gaste cota.

É essa ausência que torna seguro apontar um túnel para cá. O `app.py` do produto
(porta 5001) **nunca** deve ser exposto: `/api/criar-youtube` não tem autenticação
e escreveria playlists na conta do dono usando a cota dele.

Rodar:
    cd produto && ../.venv/bin/python avaliacao/avaliar.py
    cloudflared tunnel --url http://localhost:5002    # em outro terminal
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

DIR = Path(__file__).parent
PAR = json.loads((DIR / "par_avaliacao.json").read_text())
LOG = DIR.parent / "logs" / "eventos.jsonl"
LOG.parent.mkdir(exist_ok=True)

GABARITO = PAR.pop("_gabarito")  # nunca vai para o cliente
ESCOLHAS = {"lista_1", "lista_2", "empate"}

app = Flask(__name__, static_folder="static", static_url_path="")


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "avaliar.html")


@app.route("/api/par")
def par():
    return jsonify(PAR)


@app.route("/api/resposta", methods=["POST"])
def resposta():
    corpo = request.get_json(force=True, silent=True) or {}
    par_id = corpo.get("par")
    escolha = corpo.get("escolha")
    respondente = str(corpo.get("respondente", ""))[:64]

    if par_id not in GABARITO or escolha not in ESCOLHAS or not respondente:
        return jsonify({"erro": "resposta inválida"}), 400

    # O braço é resolvido aqui, no servidor: o cliente nunca soube qual lista era
    # qual, então a tabulação já sai pronta.
    braco = "empate" if escolha == "empate" else GABARITO[par_id][escolha]
    evento = {
        "evento": "avaliacao_escuta",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "respondente": respondente,
        "par": par_id,
        "palavras": next(p["palavras"] for p in PAR["pares"] if p["id"] == par_id),
        "escolha": escolha,
        "braco_escolhido": braco,
        "comentario": str(corpo.get("comentario", ""))[:500],
        "segundos_ouvindo": int(corpo.get("segundos", 0) or 0),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")
    print("resposta:", evento["respondente"][:8], par_id, escolha, "->", braco)
    return jsonify({"ok": True})


@app.route("/api/resultado")
def resultado():
    """Tabulação corrida, para você acompanhar enquanto as respostas chegam."""
    if not LOG.exists():
        return jsonify({"total": 0})
    contagem = {}
    for linha in LOG.read_text(encoding="utf-8").splitlines():
        e = json.loads(linha)
        if e.get("evento") != "avaliacao_escuta":
            continue
        contagem.setdefault(e["par"], {"algoritmo": 0, "aleatoria": 0, "empate": 0})
        contagem[e["par"]][e["braco_escolhido"]] += 1
    return jsonify(contagem)


if __name__ == "__main__":
    print("Avaliação em http://localhost:5002  (aponte o túnel para esta porta)")
    app.run(host="127.0.0.1", port=5002, debug=False)
