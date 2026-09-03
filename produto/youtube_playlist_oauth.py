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
import re
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DIR = Path(__file__).parent
ENTREGAS_DIR = DIR.parent / "entregas"
sys.path.insert(0, str(DIR))
from motor_playlist import PipelineMood  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/youtube"]
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


class CotaEsgotada(Exception):
    """A cota diária da YouTube Data API acabou no meio da operação.

    Erguida em vez de devolver None: com None, o laço seguia tentando e cada
    faixa restante virava uma "não encontrada" silenciosa — o usuário recebia uma
    playlist pela metade sem saber por quê."""


def _e_cota(erro):
    return erro.resp.status == 403 and b"quota" in erro.content.lower()


def buscar_video_id(youtube, track_name, artists, duracao_ms=None):
    """Devolve o video_id da melhor correspondência, ou None se não houver.

    Pega 5 candidatos (mesmo custo de cota que 1: `search.list` cobra 100
    unidades por chamada, não por resultado) e, quando a duração da faixa é
    conhecida, escolhe o de duração mais próxima, descartando quem estiver a mais
    de 25%. Sem isso, o primeiro resultado do YouTube para "nome artista" pode ser
    cover, reação, ao vivo ou "10 hours loop" — nada disso é a faixa que as Fases
    2 e 3 mediram, e a playlist toca outra coisa."""
    consulta = f"{track_name} {artists}"
    try:
        resposta = youtube.search().list(
            part="id", q=consulta, type="video", maxResults=5
        ).execute()
    except HttpError as e:
        if _e_cota(e):
            raise CotaEsgotada(consulta) from e
        print(f"  [erro na busca] {consulta}: {e}", flush=True)
        return None

    ids = [i["id"]["videoId"] for i in resposta.get("items", []) if i["id"].get("videoId")]
    if not ids:
        return None
    if duracao_ms is None:
        return ids[0]

    alvo = duracao_ms / 1000
    try:
        detalhes = youtube.videos().list(part="contentDetails", id=",".join(ids)).execute()
    except HttpError as e:
        if _e_cota(e):
            raise CotaEsgotada(consulta) from e
        return ids[0]

    duracoes = {v["id"]: _segundos(v["contentDetails"]["duration"]) for v in detalhes.get("items", [])}
    melhor, menor_erro = None, None
    for vid in ids:  # empate resolvido pela ordem de relevância do YouTube
        d = duracoes.get(vid)
        if not d:
            continue
        erro = abs(d - alvo) / alvo
        if menor_erro is None or erro < menor_erro:
            melhor, menor_erro = vid, erro
    return melhor if melhor and menor_erro <= 0.25 else None


def _segundos(iso):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def criar_playlist_youtube(youtube, titulo, descricao, video_ids, privacidade="unlisted"):
    """Cria a playlist e adiciona os vídeos, na ordem recebida.

    Devolve (url, adicionadas, falhas). Antes devolvia só a URL, e o chamador não
    tinha como saber que a playlist saiu pela metade."""
    playlist = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": titulo, "description": descricao},
            "status": {"privacyStatus": privacidade},  # "private", "unlisted" ou "public"
        },
    ).execute()
    playlist_id = playlist["id"]

    adicionadas, falhas = 0, []
    for video_id in video_ids:
        if video_id is None:
            continue
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                        # SEM "position": antes era `position: i`, o índice na lista
                        # completa. Como as faixas não encontradas são puladas, o `i`
                        # passava a apontar além do fim da playlist e o YouTube
                        # rejeitava TODAS as inserções seguintes — uma única busca
                        # falha derrubava todo o resto. Sem o campo, cada item é
                        # anexado no fim, o que já preserva a ordem relativa.
                    }
                },
            ).execute()
            adicionadas += 1
        except HttpError as e:
            if _e_cota(e):
                raise CotaEsgotada(f"após {adicionadas} faixas") from e
            falhas.append(video_id)
            print(f"  [erro ao adicionar] video_id={video_id}: {e}", flush=True)

    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    print(f"Playlist criada: {adicionadas}/{len(video_ids)} faixas adicionadas", flush=True)
    print(f"URL: {url}", flush=True)
    return url, adicionadas, falhas


def gerar_playlist_youtube_real(palavras, n=15, privacidade="unlisted"):
    """Ponta a ponta: gera a playlist com o motor único (motor_playlist.py),
    resolve cada faixa para um vídeo do YouTube, e cria a playlist real na
    conta autenticada."""
    pipeline = PipelineMood(ENTREGAS_DIR)
    playlist = pipeline.gerar_playlist(palavras, n=n)

    print(f"Playlist gerada ({len(playlist)} faixas): {' + '.join(palavras)}")
    print("Resolvendo faixas no YouTube...")

    creds = autenticar()
    youtube = build("youtube", "v3", credentials=creds)

    video_ids = []
    for _, row in playlist.iterrows():
        vid = buscar_video_id(youtube, row["track_name"], row["artists"], row.get("duration_ms"))
        video_ids.append(vid)
        print(f"  {row['track_name']} — {row['artists']}: {vid or 'NÃO ENCONTRADA'}", flush=True)

    titulo = f"[Protótipo Fase 5] {' + '.join(palavras)}"
    descricao = (
        "Playlist gerada automaticamente pelo pipeline de mood + transição suave "
        "(Fases 2-3 do projeto CBL). Não editorial — para validação por escuta."
    )
    url, _, _ = criar_playlist_youtube(youtube, titulo, descricao, video_ids, privacidade)
    return url


if __name__ == "__main__":
    # Exemplo — troque as palavras/tamanho pelo que quiser validar
    gerar_playlist_youtube_real(["Calmo", "Instrumental"], n=15, privacidade="unlisted")
