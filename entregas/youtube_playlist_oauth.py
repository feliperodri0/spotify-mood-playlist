"""
Fase 5 — Criação de playlist real no YouTube (via OAuth)
==========================================================

Cria uma playlist de verdade, salva numa conta do YouTube, a partir de uma
combinação de moods já validada nas Fases 2-4. Diferente do link de busca
usado na interface (Fase 4), isto gera uma playlist real, com URL
compartilhável, pronta pra escuta em sequência — para a validação qualitativa
da Fase 5.

IMPORTANTE — o que este script NÃO faz sozinho
------------------------------------------------
A etapa de consentimento OAuth (a tela "Permitir acesso" do Google) só pode
acontecer no SEU navegador, com a SUA conta — não existe forma de automatizar
isso a partir daqui. Antes de rodar este script, você precisa:

1. Ir em https://console.cloud.google.com/ e criar um projeto (gratuito).
2. Em "APIs e Serviços" → "Biblioteca", ativar a "YouTube Data API v3".
3. Em "APIs e Serviços" → "Credenciais" → "Criar credenciais" →
   "ID do cliente OAuth" → tipo de aplicativo "Aplicativo para computador".
4. Baixar o JSON gerado e salvar como `client_secret.json` dentro de
   `entregas/credenciais/` (essa pasta já está no `.gitignore` — nunca vai
   pro repositório). NÃO cole o conteúdo desse arquivo em conversas com IA —
   é uma credencial, trate como senha.
5. Instalar as dependências (já testadas neste ambiente):
   pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
6. Rodar este script no SEU terminal (não dá pra rodar de forma não-interativa
   num notebook headless — precisa abrir o navegador de verdade):
   python youtube_playlist_oauth.py

Na primeira execução, uma aba do navegador abre pedindo login e permissão.
Depois disso, um `token.json` fica salvo aqui e as próximas execuções não
pedem login de novo (até o token expirar).

Custo de quota (cota gratuita padrão: 10.000 unidades/dia)
------------------------------------------------------------
Cada busca de vídeo custa 100 unidades; criar a playlist custa 50; adicionar
cada faixa custa 50. Uma playlist de 20 faixas custa
20*100 + 50 + 20*50 = 3.050 unidades — dá pra gerar ~3 playlists de 20 faixas
por dia na cota padrão. NÃO é viável gerar as 460 combinações pré-computadas
da Fase 4 dessa forma (custaria ~1,4 milhão de unidades) — este script é para
gerar playlists pontuais, escolhidas à mão, para validação por escuta.
"""

import pickle
from pathlib import Path

import pandas as pd
import joblib
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube"]
DIR = Path(__file__).parent
CLIENT_SECRET_FILE = DIR / "credenciais/client_secret.json"
TOKEN_FILE = DIR / "credenciais/token.json"


def autenticar():
    """Faz o fluxo OAuth (abre o navegador na primeira vez) e devolve credenciais válidas."""
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Não encontrei {CLIENT_SECRET_FILE}. Siga os passos 1-4 no topo "
                    "deste arquivo antes de rodar o script."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            # host="127.0.0.1" explícito, não "localhost": a isenção do Google de não exigir
            # o redirect_uri pré-cadastrado vale documentadamente para o IP literal 127.0.0.1;
            # o padrão da biblioteca manda "localhost", que já causou "redirect_uri_mismatch"
            # mesmo com credencial do tipo certo ("Aplicativo para computador").
            creds = flow.run_local_server(host="127.0.0.1", port=0)  # abre o navegador aqui

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return creds


def buscar_video_id(youtube, track_name, artists):
    """Busca a faixa no YouTube e devolve o video_id do primeiro resultado (ou None)."""
    consulta = f"{track_name} {artists}"
    try:
        resposta = youtube.search().list(
            part="id", q=consulta, type="video", maxResults=1
        ).execute()
    except HttpError as e:
        print(f"  [erro na busca] {consulta}: {e}")
        return None

    itens = resposta.get("items", [])
    if not itens:
        return None
    return itens[0]["id"]["videoId"]


def criar_playlist_youtube(youtube, titulo, descricao, video_ids, privacidade="unlisted"):
    """Cria a playlist e adiciona os vídeos, na ordem recebida. Devolve a URL."""
    playlist = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": titulo, "description": descricao},
            "status": {"privacyStatus": privacidade},  # "private", "unlisted" ou "public"
        },
    ).execute()
    playlist_id = playlist["id"]

    adicionadas, nao_encontradas = 0, []
    for i, video_id in enumerate(video_ids):
        if video_id is None:
            continue
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                        "position": i,
                    }
                },
            ).execute()
            adicionadas += 1
        except HttpError as e:
            print(f"  [erro ao adicionar] video_id={video_id}: {e}")

    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    print(f"Playlist criada: {adicionadas}/{len(video_ids)} faixas adicionadas")
    print(f"URL: {url}")
    return url


def gerar_playlist_youtube_real(palavras, n=15, privacidade="unlisted"):
    """Ponta a ponta: gera a playlist com o motor da Fase 4, resolve cada faixa
    para um vídeo do YouTube, e cria a playlist real na conta autenticada."""
    modelo = joblib.load(DIR / "modelo_mood.joblib")
    pt, scaler, knn = modelo["power_transformer"], modelo["scaler"], modelo["knn"]
    features, cols_assimetricas = modelo["features"], modelo["cols_assimetricas"]
    vocab_df, vocab_X = modelo["vocab_df"], modelo["vocab_X"]

    df_clean = pd.read_parquet(DIR / "df_clean.parquet")
    mood_df = pd.read_parquet(DIR / "catalogo_com_mood.parquet")
    assert (df_clean["track_id"].values == mood_df["track_id"].values).all()
    df = df_clean.copy()
    df["mood"] = mood_df["mood"].values

    X_raw = df[features].copy()
    X_raw[cols_assimetricas] = pt.transform(X_raw[cols_assimetricas])
    X = scaler.transform(X_raw[features])

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

    df["camelot"] = df.apply(lambda r: camelot(int(r["key"]), int(r["mode"])), axis=1)

    def selecionar_candidatas(palavras, n):
        indices_ancoras = [vocab_df.index.get_loc(p) for p in palavras]
        alvo = vocab_X[indices_ancoras].mean(axis=0).reshape(1, -1)
        multiplicador = 6
        while True:
            k = min(n * multiplicador, len(df))
            distancias, indices = knn.kneighbors(alvo, n_neighbors=k)
            vistos, idx_finais = set(), []
            for idx_faixa in indices[0]:
                linha = df.iloc[idx_faixa]
                chave = (linha["track_name"], linha["artists"])
                if chave not in vistos:
                    vistos.add(chave)
                    idx_finais.append(idx_faixa)
                if len(idx_finais) == n:
                    break
            if len(idx_finais) == n or k >= len(df):
                break
            multiplicador *= 2
        return df.iloc[idx_finais].reset_index(drop=True), X[idx_finais]

    def sequenciar(candidatas, X_candidatas, peso_tempo=0.5, peso_harmonico=1.0):
        import numpy as np
        from scipy.spatial.distance import cdist

        n_ = len(candidatas)
        custo = cdist(X_candidatas, X_candidatas)
        tempos = candidatas["tempo"].values
        dist_tempo = np.abs(tempos[:, None] - tempos[None, :]) / df["tempo"].std()
        camelots = candidatas["camelot"].tolist()
        for i in range(n_):
            for j in range(n_):
                if i != j:
                    custo[i, j] += peso_tempo * dist_tempo[i, j] + peso_harmonico * penalidade_harmonica(
                        camelots[i], camelots[j]
                    )
        visitado, atual, restante = [0], 0, set(range(1, n_))
        while restante:
            proximo = min(restante, key=lambda j: custo[atual, j])
            visitado.append(proximo)
            restante.remove(proximo)
            atual = proximo
        return candidatas.iloc[visitado].reset_index(drop=True)

    candidatas, X_cand = selecionar_candidatas(palavras, n)
    playlist = sequenciar(candidatas, X_cand)

    print(f"Playlist gerada ({len(playlist)} faixas): {' + '.join(palavras)}")
    print("Resolvendo faixas no YouTube...")

    creds = autenticar()
    youtube = build("youtube", "v3", credentials=creds)

    video_ids = []
    for _, row in playlist.iterrows():
        vid = buscar_video_id(youtube, row["track_name"], row["artists"])
        video_ids.append(vid)
        status = vid if vid else "NÃO ENCONTRADA"
        print(f"  {row['track_name']} — {row['artists']}: {status}")

    titulo = f"[Protótipo Fase 5] {' + '.join(palavras)}"
    descricao = (
        "Playlist gerada automaticamente pelo pipeline de mood + transição suave "
        "(Fases 2-3 do projeto CBL). Não editorial — para validação por escuta."
    )
    return criar_playlist_youtube(youtube, titulo, descricao, video_ids, privacidade)


if __name__ == "__main__":
    # Exemplo — troque as palavras/tamanho pelo que quiser validar
    gerar_playlist_youtube_real(["Calmo", "Instrumental"], n=15, privacidade="unlisted")
