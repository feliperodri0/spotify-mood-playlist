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


NOME_PT = {
    "energy": "energia", "valence": "felicidade", "danceability": "dançabilidade",
    "acousticness": "acústica", "instrumentalness": "instrumental", "speechiness": "fala",
}


class MoodsContraditorios(Exception):
    """Duas palavras pedidas se contradizem: uma exige uma característica alta e
    a outra exige a mesma característica baixa.

    Erguida em vez de devolver silenciosamente faixas do centro do acervo. Com a
    regra da média (anterior), `Feliz + Melancolico` devolvia energy 0,55 /
    valence 0,50 — exatamente a média do catálogo, que não é nem uma coisa nem
    outra. Falhar alto e explicar é um produto melhor que acertar por fora.

    O teste é feito sobre as ÂNCORAS, não sobre o resultado da busca: contradição
    é uma propriedade do vocabulário. Tentativas de detectá-la pela geometria do
    resultado (distância mediana ao catálogo, razão contra o que a palavra entrega
    sozinha) foram medidas e não separam os casos — em 6 dimensões a distância
    dilui a palavra: `Calmo+Instrumental` (compatível) aparece 12,8x pior que
    sozinho, enquanto `Feliz+Melancolico` (impossível) aparece 6,8x."""

    def __init__(self, palavra_a, palavra_b, caracteristicas):
        self.palavra_a, self.palavra_b = palavra_a, palavra_b
        self.caracteristicas = caracteristicas
        traduzidas = " e ".join(NOME_PT.get(f, f) for f in caracteristicas)
        alta, baixa = ("altas", "baixas") if len(caracteristicas) > 1 else ("alta", "baixa")
        super().__init__(
            f"{palavra_a} e {palavra_b} se contradizem: um pede {traduzidas} {alta}, "
            f"o outro pede {baixa}. Nenhuma música do catálogo é as duas."
        )


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

        self.duracao_mediana = float(self.df["duration_ms"].median())

        self.df["camelot"] = self.df.apply(lambda r: camelot(int(r["key"]), int(r["mode"])), axis=1)

        # Perfil de cada âncora: para cada feature, a palavra pede "alto", "baixo"
        # ou não se importa. Base do teste de contradição (ver MoodsContraditorios).
        baixo, alto = self.df[self.features].quantile(0.33), self.df[self.features].quantile(0.66)
        self.perfil_ancoras = {
            palavra: {
                f: ("alto" if v > alto[f] else "baixo" if v < baixo[f] else None)
                for f, v in self.vocab_df.loc[palavra, self.features].items()
            }
            for palavra in self.vocabulario
        }

    def selecionar_candidatas(self, palavras, n=20):
        """Candidatas que atendem **todas** as palavras pedidas, não a média delas.

        Antes: o alvo era o ponto médio entre as âncoras. Isso dissolvia a palavra
        — medido no produto, `Calmo + Instrumental` devolvia instrumentalness média
        0,118 (contra 0,711 quando `Instrumental` vai sozinho), porque o ponto médio
        entre "instrumental" e "não instrumental" é "meio instrumental", que na
        prática é o centro do catálogo. Com 3 palavras piorava: 0,055.

        Agora: cada candidata é ranqueada pela distância à âncora **mais distante**
        (pior caso). Uma faixa só sobe se estiver razoavelmente perto de todas as
        palavras. Com uma palavra só, isso é idêntico ao k-NN de antes.

        A deduplicação por (track_name, artists) e o escalonamento da busca seguem
        iguais — resolvem duplicatas de catálogo (~9,4%), não têm relação com esta
        mudança."""
        self.verificar_contradicao(palavras)
        indices_ancoras = [self.vocab_df.index.get_loc(p) for p in palavras]
        ancoras = self.vocab_X[indices_ancoras]

        multiplicador = 6
        while True:
            k = min(n * multiplicador, len(self.df))
            # Um pool por âncora (o índice k-NN segue sendo o que busca), unidos e
            # depois reordenados pelo pior caso. Buscar em torno da média não serve:
            # a região do meio pode não conter nenhuma faixa boa para as duas palavras.
            pool = set()
            for ancora in ancoras:
                _, indices = self.knn.kneighbors(ancora.reshape(1, -1), n_neighbors=k)
                pool.update(int(i) for i in indices[0])
            pool = np.fromiter(pool, dtype=int, count=len(pool))

            distancias = cdist(self.X[pool], ancoras)
            pior_caso = distancias.max(axis=1)
            ordenados = pool[np.argsort(pior_caso, kind="stable")]

            vistos, idx_finais = set(), []
            for idx_faixa in ordenados:
                linha = self.df.iloc[idx_faixa]
                chave = (linha["track_name"], linha["artists"])
                if chave not in vistos:
                    vistos.add(chave)
                    idx_finais.append(int(idx_faixa))
                if len(idx_finais) == n:
                    break
            if len(idx_finais) == n or k >= len(self.df):
                break
            multiplicador *= 2

        return self.df.iloc[idx_finais].reset_index(drop=True), self.X[idx_finais]

    def verificar_contradicao(self, palavras):
        """Ergue MoodsContraditorios se duas das palavras pedidas exigem lados
        opostos da mesma característica. Barato: só olha as âncoras."""
        for i, a in enumerate(palavras):
            for b in palavras[i + 1:]:
                opostas = [
                    f for f in self.features
                    if {self.perfil_ancoras[a][f], self.perfil_ancoras[b][f]} == {"alto", "baixo"}
                ]
                if opostas:
                    raise MoodsContraditorios(a, b, opostas)

    def combinacoes_possiveis(self):
        """Pares de palavras que NÃO se contradizem — o front usa para desabilitar
        as opções impossíveis antes do clique, em vez de errar depois."""
        return {
            palavra: sorted(
                outra for outra in self.vocabulario
                if outra != palavra and not self._conflito(palavra, outra)
            )
            for palavra in self.vocabulario
        }

    def _conflito(self, a, b):
        return any(
            {self.perfil_ancoras[a][f], self.perfil_ancoras[b][f]} == {"alto", "baixo"}
            for f in self.features
        )

    def sequenciar(self, candidatas, X_candidatas, peso_tempo=0.5, peso_harmonico=1.0, inicio=0):
        """Ordena as candidatas por transição suave, partindo de `inicio`.

        `inicio` era fixo em 0 (a candidata mais próxima da âncora), o que fazia
        o mesmo pedido devolver sempre a mesma playlist, byte a byte. Agora é a
        faixa que o usuário escolheu como ponto de partida."""
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
        inicio = int(inicio) if 0 <= int(inicio) < n else 0
        visitado, atual = [inicio], inicio
        restante = set(range(n)) - {inicio}
        while restante:
            proximo = min(restante, key=lambda j: custo[atual, j])
            visitado.append(proximo)
            restante.remove(proximo)
            atual = proximo
        return candidatas.iloc[visitado].reset_index(drop=True)

    def gerar_playlist(self, palavras, n=20, faixa_inicial=None):
        """Playlist por número de faixas. `faixa_inicial` é um track_id que passa
        a ser a primeira faixa; ignorado se não estiver entre as candidatas."""
        candidatas, X_cand = self.selecionar_candidatas(palavras, n=n)
        return self.sequenciar(candidatas, X_cand, inicio=self._indice_de(candidatas, faixa_inicial))

    def gerar_playlist_por_duracao(self, palavras, minutos, faixa_inicial=None, teto_faixas=30):
        """Playlist com duração-alvo em vez de contagem de faixas.

        Busca candidatas com folga sobre a estimativa (a duração mediana do
        catálogo é 3,5 min, mas a variação é grande), ordena por transição suave e
        corta no prefixo cuja soma chega mais perto do alvo. Aceita passar até 10%
        do pedido: parar sempre antes fazia "15 minutos" virar 10, o que erra mais
        do que devolver 16."""
        alvo_ms = float(minutos) * 60_000
        # 1,6x de folga: o corte precisa de candidatas sobrando para escolher onde
        # parar, e candidata extra que não entra não custa nada.
        estimativa = int(alvo_ms / self.duracao_mediana * 1.6) + 2
        n = max(2, min(estimativa, teto_faixas))

        candidatas, X_cand = self.selecionar_candidatas(palavras, n=n)
        ordenada = self.sequenciar(candidatas, X_cand, inicio=self._indice_de(candidatas, faixa_inicial))

        acumulado, melhor_corte, melhor_erro = 0.0, 1, None
        for i, duracao in enumerate(ordenada["duration_ms"].values):
            acumulado += duracao
            if acumulado > alvo_ms * 1.1:
                break
            erro = abs(acumulado - alvo_ms)
            if melhor_erro is None or erro < melhor_erro:
                melhor_corte, melhor_erro = i + 1, erro
        return ordenada.iloc[:melhor_corte].reset_index(drop=True)

    @staticmethod
    def _indice_de(candidatas, track_id):
        if not track_id:
            return 0
        posicoes = candidatas.index[candidatas["track_id"] == track_id].tolist()
        return int(posicoes[0]) if posicoes else 0

    def faixas_por_id(self, track_ids):
        """Devolve as faixas na ORDEM dos ids recebidos.

        É o que permite a prévia ser o contrato: o front devolve os track_id que o
        usuário aprovou e o backend cria exatamente aquilo, em vez de regerar a
        playlist e torcer para dar igual."""
        indexado = self.df.set_index("track_id")
        presentes = [i for i in track_ids if i in indexado.index]
        return indexado.loc[presentes].reset_index()

    @staticmethod
    def playlist_para_registros(playlist):
        saida = playlist.assign(
            camelot_str=playlist["camelot"].apply(lambda c: f"{c[0]}{c[1]}"),
            duracao=playlist["duration_ms"].apply(lambda ms: f"{int(ms) // 60000}:{int(ms) // 1000 % 60:02d}"),
        )
        # track_id e duração vão junto: o front precisa do id para escolher a
        # faixa inicial e para devolver a prévia aprovada na hora de criar.
        return saida[[
            "track_id", "track_name", "artists", "tempo", "track_genre", "mood",
            "camelot_str", "duracao", "duration_ms",
        ]].rename(columns={"camelot_str": "camelot"}).to_dict("records")
