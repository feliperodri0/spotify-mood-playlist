"""Testes da busca de faixa e da garantia de semente (ticket #1).

Carrega o catálogo real (~2s) em vez de um dublê: o comportamento sob teste
(dedup por duplicatas reais de catalogação, popularidade real, uma faixa fora
das candidatas naturais de um clima) só existe nos dados de verdade.

Rodar:
    .venv/bin/python produto/tests/test_busca_faixa.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor_playlist import PipelineMood  # noqa: E402

PIPELINE = None


def pipeline():
    global PIPELINE
    if PIPELINE is None:
        PIPELINE = PipelineMood(Path(__file__).resolve().parents[2] / "entregas")
    return PIPELINE


def test_busca_ignora_consulta_curta_demais():
    assert pipeline().buscar_faixas("a") == []
    assert pipeline().buscar_faixas("") == []


def test_busca_por_nome_e_case_insensitive():
    resultados = pipeline().buscar_faixas("happier")
    nomes = {r["track_name"] for r in resultados}
    assert "Happier" in nomes, f"esperava achar 'Happier', veio {nomes}"


def test_busca_por_artista():
    resultados = pipeline().buscar_faixas("Marshmello")
    assert resultados, "esperava pelo menos um resultado para 'Marshmello'"
    assert all("marshmello" in r["artists"].casefold() for r in resultados)


def test_busca_dedup_por_nome_e_artista():
    # "Happier" (Marshmello;Bastille) tem 46 linhas no catálogo bruto -- a
    # busca deve devolver UMA entrada, não 46.
    resultados = pipeline().buscar_faixas("Happier")
    chaves = [(r["track_name"], r["artists"]) for r in resultados]
    assert len(chaves) == len(set(chaves)), f"duplicata não removida: {chaves}"


def test_busca_respeita_o_limite():
    resultados = pipeline().buscar_faixas("love", limite=3)
    assert len(resultados) <= 3


def test_garantir_semente_nao_mexe_se_ja_esta_nas_candidatas():
    p = pipeline()
    candidatas, X = p.selecionar_candidatas(["Calmo"], n=5)
    presente = candidatas.iloc[2]["track_id"]
    nova_c, nova_x = p._garantir_semente(candidatas, X, presente)
    assert nova_c["track_id"].tolist() == candidatas["track_id"].tolist()
    assert (nova_x == X).all()


def test_garantir_semente_forca_faixa_fora_do_clima():
    p = pipeline()
    # Uma faixa claramente do lado "Energetico/Intenso" do catálogo, forçada
    # como semente de um pedido "Calmo" -- não seria escolhida naturalmente.
    candidatas_calmo, _ = p.selecionar_candidatas(["Calmo"], n=5)
    candidatas_energetico, _ = p.selecionar_candidatas(["Energetico"], n=30)
    fora = candidatas_energetico.iloc[-1]["track_id"]
    assert fora not in candidatas_calmo["track_id"].values, "a faixa escolhida já seria candidata natural"

    playlist = p.gerar_playlist(["Calmo"], n=5, faixa_inicial=fora)
    assert playlist.iloc[0]["track_id"] == fora, "a playlist não começou pela semente forçada"
    assert len(playlist) == 5, "o tamanho pedido não foi preservado"


def test_garantir_semente_id_inexistente_nao_quebra():
    p = pipeline()
    playlist = p.gerar_playlist(["Calmo"], n=5, faixa_inicial="id_que_nao_existe_00000")
    assert len(playlist) == 5


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok:", nome)
    print("todos passaram")
