"""
Resolve os `video_id` do par congelado. GASTA COTA — rode uma vez só.

Custo: 100 unidades por faixa (search.list) + 1 por lote de durações
(videos.list). Com 2 pares x 8 faixas x 2 listas, as faixas se repetem entre as
listas (é o mesmo conjunto em outra ordem), então são 16 buscas únicas: ~1.600
das 10.000 unidades diárias.

Blindagem (decisão da Q4 da grelha): em vez do primeiro resultado de
`"{nome} {artista}"`, pega 5 candidatos — mesmo custo de cota — e escolhe o de
duração mais próxima da faixa do dataset, descartando quem estiver a mais de 25%
de distância. É o que evita cover, reação, ao vivo e "10 hours loop" entrando
como se fosse a faixa medida nas Fases 2 e 3.

Rodar:
    cd produto && ../.venv/bin/python avaliacao/resolver_videos.py
"""

import json
import re
import sys
from pathlib import Path

from googleapiclient.discovery import build

DIR = Path(__file__).parent
sys.path.insert(0, str(DIR.parent))
from youtube_playlist_oauth import autenticar  # noqa: E402

TOLERANCIA = 0.25


def segundos_iso(duracao):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duracao or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def resolver(youtube, faixa):
    alvo = int(faixa["duracao"].split(":")[0]) * 60 + int(faixa["duracao"].split(":")[1])
    busca = youtube.search().list(
        part="id", q=f"{faixa['track_name']} {faixa['artists']}", type="video", maxResults=5
    ).execute()
    ids = [i["id"]["videoId"] for i in busca.get("items", [])]
    if not ids:
        return None, "sem resultado"

    detalhes = youtube.videos().list(part="contentDetails", id=",".join(ids)).execute()
    duracoes = {v["id"]: segundos_iso(v["contentDetails"]["duration"]) for v in detalhes.get("items", [])}

    melhor, melhor_erro = None, None
    for vid in ids:  # empate resolvido pela ordem do YouTube (relevância)
        d = duracoes.get(vid)
        if not d:
            continue
        erro = abs(d - alvo) / alvo
        if melhor_erro is None or erro < melhor_erro:
            melhor, melhor_erro = vid, erro
    if melhor is None or melhor_erro > TOLERANCIA:
        return None, f"nenhum candidato dentro de {int(TOLERANCIA * 100)}% da duração ({alvo}s)"
    return melhor, f"erro de duração {melhor_erro:.0%}"


def main():
    caminho = DIR / "par_avaliacao.json"
    dados = json.loads(caminho.read_text())
    youtube = build("youtube", "v3", credentials=autenticar())

    cache, falhas = {}, []
    for par in dados["pares"]:
        for lista in ("lista_1", "lista_2"):
            for faixa in par[lista]:
                chave = faixa["track_id"]
                if chave not in cache:
                    vid, nota = resolver(youtube, faixa)
                    cache[chave] = vid
                    print(f"  {faixa['track_name'][:40]:<40} {vid or 'NÃO RESOLVIDA'} ({nota})")
                    if vid is None:
                        falhas.append(f"{faixa['track_name']} — {faixa['artists']}")
                faixa["video_id"] = cache[chave]

    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2))
    print(f"\n{sum(1 for v in cache.values() if v)}/{len(cache)} faixas resolvidas. Cota usada: ~{len(cache) * 100 + len(cache)} unidades.")
    if falhas:
        print("Sem vídeo (troque a faixa ou o par):")
        for f in falhas:
            print("  -", f)


if __name__ == "__main__":
    main()
