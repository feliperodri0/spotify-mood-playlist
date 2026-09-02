"""
Motor único de geração de playlist — Fases 2 e 3
===================================================

Fonte única de verdade para "seleção de candidatas por mood" + "sequenciamento
por transição suave". Antes desta refatoração, essa lógica estava copiada em
4 lugares diferentes (modelo_mood_clustering.ipynb, sequenciamento_playlist.ipynb,
interface_playlist.ipynb, youtube_playlist_oauth.py) — o que já causou um bug
real (a correção de deduplicação/busca escalonada precisou ser replicada
manualmente nas 3 cópias existentes). Este módulo existe pra isso não
acontecer de novo com uma 4ª cópia (o script do Spotify).

Os notebooks continuam com suas próprias cópias (documentam o raciocínio
passo a passo, propositalmente) — este módulo é para os scripts/produto que
vêm depois do notebook, onde reuso pesa mais que a narrativa didática.
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

CAMELOT_MAIOR = {0: 8, 1: 3, 2: 10, 3: 5, 4: 12, 5: 7, 6: 2, 7: 9, 8: 4, 9: 11, 10: 6, 11: 1}
CAMELOT_MENOR = {0: 5, 1: 12, 2: 7, 3: 2, 4: 9, 5: 4, 6: 11, 7: 6, 8: 1, 9: 8, 10: 3, 11: 10}


def camelot(key, mode):
    numero = CAMELOT_MAIOR[key] if mode == 1 else CAMELOT_MENOR[key]
    return (numero, "B" if mode == 1 else "A")


def penalidade_harmonica(a, b):
    (na, la), (nb, lb) = a, b
    if na == nb and la == lb:
        return 0.0
    if na == nb and la != lb:
        return 0.15
    diferenca = min((na - nb) % 12, (nb - na) % 12)
    if diferenca == 1 and la == lb:
        return 0.15
    return 0.5


class PipelineMood:
    """Carrega o catálogo + artefatos da Fase 2 uma única vez e expõe
    seleção de candidatas + sequenciamento prontos pra uso."""

    def __init__(self, entregas_dir):
        entregas_dir = Path(entregas_dir)
        modelo = joblib.load(entregas_dir / "modelo_mood.joblib")
        self.pt = modelo["power_transformer"]
        self.scaler = modelo["scaler"]
        self.knn = modelo["knn"]
        self.features = modelo["features"]
        self.cols_assimetricas = modelo["cols_assimetricas"]
        self.vocab_df = modelo["vocab_df"]
        self.vocab_X = modelo["vocab_X"]
        self.vocabulario = list(self.vocab_df.index)

        df_clean = pd.read_parquet(entregas_dir / "df_clean.parquet")
        mood_df = pd.read_parquet(entregas_dir / "catalogo_com_mood.parquet")
        assert (df_clean["track_id"].values == mood_df["track_id"].values).all(), "ordem das linhas não bate"
        self.df = df_clean.copy()
        self.df["mood"] = mood_df["mood"].values

        X_raw = self.df[self.features].copy()
        X_raw[self.cols_assimetricas] = self.pt.transform(X_raw[self.cols_assimetricas])
        self.X = self.scaler.transform(X_raw[self.features])

        self.df["camelot"] = self.df.apply(lambda r: camelot(int(r["key"]), int(r["mode"])), axis=1)

    def selecionar_candidatas(self, palavras, n=20):
        """Busca vizinhos em excesso e deduplica por (track_name, artists) — necessário porque
        o catálogo tem duplicatas por track_id repetido em gênero (Passo 2.2 do EDA) e músicas
        reeditadas sob track_id diferente (~9,4% do catálogo, achado da Fase 3). Se o multiplicador
        inicial não trouxer candidatas únicas suficientes, a busca escalona (dobra o raio) em vez
        de silenciosamente devolver menos faixas que o pedido."""
        indices_ancoras = [self.vocab_df.index.get_loc(p) for p in palavras]
        alvo = self.vocab_X[indices_ancoras].mean(axis=0).reshape(1, -1)

        multiplicador = 6
        while True:
            k = min(n * multiplicador, len(self.df))
            distancias, indices = self.knn.kneighbors(alvo, n_neighbors=k)
            vistos, idx_finais = set(), []
            for idx_faixa in indices[0]:
                linha = self.df.iloc[idx_faixa]
                chave = (linha["track_name"], linha["artists"])
                if chave not in vistos:
                    vistos.add(chave)
                    idx_finais.append(idx_faixa)
                if len(idx_finais) == n:
                    break
            if len(idx_finais) == n or k >= len(self.df):
                break
            multiplicador *= 2

        return self.df.iloc[idx_finais].reset_index(drop=True), self.X[idx_finais]

    def sequenciar(self, candidatas, X_candidatas, peso_tempo=0.5, peso_harmonico=1.0):
        n = len(candidatas)
        custo = cdist(X_candidatas, X_candidatas)
        tempos = candidatas["tempo"].values
        dist_tempo = np.abs(tempos[:, None] - tempos[None, :]) / self.df["tempo"].std()
        camelots = candidatas["camelot"].tolist()
        for i in range(n):
            for j in range(n):
                if i != j:
                    custo[i, j] += peso_tempo * dist_tempo[i, j] + peso_harmonico * penalidade_harmonica(
                        camelots[i], camelots[j]
                    )
        visitado, atual, restante = [0], 0, set(range(1, n))
        while restante:
            proximo = min(restante, key=lambda j: custo[atual, j])
            visitado.append(proximo)
            restante.remove(proximo)
            atual = proximo
        return candidatas.iloc[visitado].reset_index(drop=True)

    def gerar_playlist(self, palavras, n=20):
        candidatas, X_cand = self.selecionar_candidatas(palavras, n=n)
        return self.sequenciar(candidatas, X_cand)

    @staticmethod
    def playlist_para_registros(playlist):
        saida = playlist.assign(camelot_str=playlist["camelot"].apply(lambda c: f"{c[0]}{c[1]}"))
        return saida[["track_name", "artists", "tempo", "track_genre", "mood", "camelot_str"]].rename(
            columns={"camelot_str": "camelot"}
        ).to_dict("records")
