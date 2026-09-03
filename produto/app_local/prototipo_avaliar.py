"""
PROTÓTIPO DESCARTÁVEL — não é código de produção.
=================================================

Pergunta que este protótipo responde: **como deve ser a tela de avaliação cega
(`/avaliar`)?** Três variantes, trocáveis por `?variant=A|B|C`, numa rota
descartável. Serve dados REAIS do motor (mesmas 8 faixas em duas ordens), mas
nenhum player real: os players são stubs com a proporção certa, porque a
resolução dos video_id gasta cota da YouTube Data API e a pergunta aqui é de
layout, não de backend.

Servidor separado de propósito: o `app.py` real não é tocado, então nada deste
protótipo pode vazar para o produto.

Rodar:
    cd produto/app_local
    ../../.venv/bin/python prototipo_avaliar.py
Depois abrir http://localhost:5002/?variant=A

Quando uma variante ganhar: dobrar a vencedora no produto de verdade
(reescrita, não copiada) e mandar este arquivo + o .html para o branch
descartável. Não promover direto.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Flask, jsonify, send_from_directory

DIR = Path(__file__).parent
PRODUTO = DIR.parent
ENTREGAS = PRODUTO.parent / "entregas"
sys.path.insert(0, str(PRODUTO))

from motor_playlist import PipelineMood, penalidade_harmonica  # noqa: E402

# Par fixo do teste: mesmas faixas, duas ordens. Semente fixa para o par ser
# reproduzível — decisão da Q5 da grelha (aleatório, mas auditável).
PALAVRAS = ["Calmo", "Instrumental"]
N_FAIXAS = 8
SEMENTE = 20260902

app = Flask(__name__, static_folder="static", static_url_path="")

print("Carregando o motor (113k faixas, demora alguns segundos)...")
pipeline = PipelineMood(ENTREGAS)
print("Catálogo carregado:", len(pipeline.df), "faixas")


def metricas(ordem: pd.DataFrame) -> dict:
    """As duas métricas do projeto, para conferência do pesquisador — NUNCA
    exibidas ao respondente (a avaliação é cega)."""
    tempos = ordem["tempo"].values
    saltos = np.abs(np.diff(tempos))
    camelots = ordem["camelot"].tolist()
    penas = [penalidade_harmonica(camelots[i], camelots[i + 1]) for i in range(len(camelots) - 1)]
    compat = sum(1 for p in penas if p <= 0.15) / len(penas)
    return {"delta_bpm": round(float(saltos.mean()), 1), "pct_compativel": round(compat * 100)}


def montar_par():
    candidatas, X = pipeline.selecionar_candidatas(PALAVRAS, n=N_FAIXAS)
    algoritmo = pipeline.sequenciar(candidatas, X)
    rng = np.random.default_rng(SEMENTE)
    aleatoria = candidatas.iloc[rng.permutation(len(candidatas))].reset_index(drop=True)

    def faixas(ordem):
        registros = PipelineMood.playlist_para_registros(ordem)
        for r, dur in zip(registros, ordem["duration_ms"].values):
            r["tempo"] = round(float(r["tempo"]))
            r["duracao"] = f"{int(dur) // 60000}:{int(dur) // 1000 % 60:02d}"
        return registros

    return {
        # As listas chegam ao front sem dizer qual é qual: "lista_1"/"lista_2".
        "lista_1": faixas(algoritmo),
        "lista_2": faixas(aleatoria),
        "palavras": PALAVRAS,
        "semente": SEMENTE,
        # Só para o pesquisador, atrás do botão "revelar" da barra de protótipo.
        "_gabarito": {
            "lista_1": {"braco": "algoritmo", **metricas(algoritmo)},
            "lista_2": {"braco": "aleatória", **metricas(aleatoria)},
        },
    }


PAR = montar_par()
print("Par montado:", PAR["_gabarito"])


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "prototipo_avaliar.html")


@app.route("/api/prototipo/par")
def par():
    return jsonify(PAR)


if __name__ == "__main__":
    print("PROTÓTIPO — abra http://localhost:5002/?variant=A")
    app.run(host="127.0.0.1", port=5002, debug=False)
