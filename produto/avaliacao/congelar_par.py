"""
Congela os pares do teste de escuta em `avaliacao/par_avaliacao.json`.

Roda UMA vez. Depois disso o servidor de avaliação (`avaliar.py`) só lê esse
arquivo — ele não carrega o motor, não abre o catálogo e não toca na API do
YouTube. É essa separação que torna seguro expor a avaliação por túnel.

Desenho do par (decisões da grelha):
- Gera com n=30 e apresenta um RECORTE de 8 faixas consecutivas. Medido: com 8
  candidatas o algoritmo bate o aleatório por 1,7x (Δ 15,2 vs 25,2 BPM); com 30,
  por 3,5x (8,7 vs 30,1). Testar com 8 candidatas mediria o sistema no regime
  onde ele é mais fraco; 30 faixas ninguém ouve. O recorte resolve os dois.
- O braço aleatório embaralha exatamente as mesmas 8 faixas: isola a ORDEM.
- Qual braço vira "Lista 1" é sorteado por par e guardado em `_gabarito`, que o
  servidor nunca envia ao respondente.
- Os `video_id` ficam null aqui: resolvê-los gasta cota da YouTube Data API
  (100 unidades por faixa) e é um passo separado, `resolver_videos.py`.

Rodar:
    cd produto && ../.venv/bin/python avaliacao/congelar_par.py
"""

import json
import sys
from pathlib import Path

import numpy as np

DIR = Path(__file__).parent
PRODUTO = DIR.parent
sys.path.insert(0, str(PRODUTO))

from motor_playlist import PipelineMood, penalidade_harmonica  # noqa: E402

SEMENTE = 20260902
N_GERADO = 30
N_RECORTE = 8
PARES = [
    # Palavra única: é o caso já documentado em roteiroSequenciamento.md (Energetico,
    # n=30 → 10,5 BPM / 72%), então o teste de escuta dialoga com aquele número.
    {"id": "par1", "palavras": ["Energetico"]},
    # Duas palavras sob a regra de interseção: valida de graça a correção do
    # achado da média de âncoras (instrumentalness 0,118 → 0,430).
    {"id": "par2", "palavras": ["Calmo", "Instrumental"]},
]


def metricas(ordem):
    saltos = np.abs(np.diff(ordem["tempo"].values))
    c = ordem["camelot"].tolist()
    pen = [penalidade_harmonica(c[i], c[i + 1]) for i in range(len(c) - 1)]
    return {
        "delta_bpm": round(float(saltos.mean()), 1),
        "pct_compativel": round(100 * sum(1 for x in pen if x <= 0.15) / len(pen)),
    }


def faixas(ordem):
    saida = []
    for _, r in ordem.iterrows():
        saida.append({
            "track_id": r["track_id"],
            "track_name": r["track_name"],
            "artists": r["artists"],
            "duracao": f"{int(r['duration_ms']) // 60000}:{int(r['duration_ms']) // 1000 % 60:02d}",
            "video_id": None,  # preenchido por resolver_videos.py
        })
    return saida


def main():
    pipeline = PipelineMood(PRODUTO.parent / "entregas")
    rng = np.random.default_rng(SEMENTE)
    saida = {"semente": SEMENTE, "n_gerado": N_GERADO, "n_recorte": N_RECORTE, "pares": [], "_gabarito": {}}

    for spec in PARES:
        candidatas, X = pipeline.selecionar_candidatas(spec["palavras"], n=N_GERADO)
        completa = pipeline.sequenciar(candidatas, X)

        inicio = (N_GERADO - N_RECORTE) // 2  # janela do meio, longe da faixa-semente
        recorte = completa.iloc[inicio:inicio + N_RECORTE].reset_index(drop=True)
        embaralhada = recorte.iloc[rng.permutation(N_RECORTE)].reset_index(drop=True)
        if embaralhada["track_id"].tolist() == recorte["track_id"].tolist():
            raise SystemExit("o embaralhamento saiu idêntico à ordem do algoritmo; troque a semente")

        # Sorteio de qual braço vira Lista 1 — o respondente não pode inferir pela posição.
        algoritmo_primeiro = bool(rng.integers(2))
        l1, l2 = (recorte, embaralhada) if algoritmo_primeiro else (embaralhada, recorte)

        saida["pares"].append({
            "id": spec["id"], "palavras": spec["palavras"],
            "lista_1": faixas(l1), "lista_2": faixas(l2),
        })
        saida["_gabarito"][spec["id"]] = {
            "lista_1": "algoritmo" if algoritmo_primeiro else "aleatoria",
            "lista_2": "aleatoria" if algoritmo_primeiro else "algoritmo",
            "metricas_recorte": {"algoritmo": metricas(recorte), "aleatoria": metricas(embaralhada)},
            "metricas_completa_30": metricas(completa),
        }

    destino = DIR / "par_avaliacao.json"
    destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2))
    print("escrito:", destino)
    for pid, g in saida["_gabarito"].items():
        print(f"  {pid}: lista_1={g['lista_1']} | recorte alg {g['metricas_recorte']['algoritmo']} "
              f"vs aleat {g['metricas_recorte']['aleatoria']} | completa30 {g['metricas_completa_30']}")


if __name__ == "__main__":
    main()
