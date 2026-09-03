"""Testes da compatibilidade de mood por semente (ticket #3).

Rodar:
    .venv/bin/python produto/tests/test_moods_compativeis.py
"""

import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor_playlist import PipelineMood  # noqa: E402

PIPELINE = None


def pipeline():
    global PIPELINE
    if PIPELINE is None:
        PIPELINE = PipelineMood(Path(__file__).resolve().parents[2] / "entregas")
    return PIPELINE


def test_id_inexistente_devolve_lista_vazia():
    assert pipeline().moods_compativeis("id_que_nao_existe_00000") == []


def test_sempre_devolve_k_moods():
    p = pipeline()
    rng = np.random.default_rng(7)
    amostra = rng.choice(p.df["track_id"].values, 50, replace=False)
    for tid in amostra:
        assert len(p.moods_compativeis(tid, k=3)) == 3, f"faixa {tid} não fechou 3 moods"


def test_nunca_devolve_par_oposto():
    p = pipeline()
    rng = np.random.default_rng(7)
    amostra = rng.choice(p.df["track_id"].values, 300, replace=False)
    for tid in amostra:
        compat = p.moods_compativeis(tid, k=3)
        for a, b in itertools.combinations(compat, 2):
            assert not p._conflito(a, b), f"faixa {tid}: {a} e {b} são opostos, ambos liberados"


def test_versoes_diferentes_da_mesma_faixa_dao_moods_diferentes():
    # "Firework": versão acústica (Canyon City) e a original (Katy Perry) têm
    # perfis opostos -- achado da grelha original.
    p = pipeline()
    linhas = p.df[p.df.track_name == "Firework"]
    acustica = linhas[linhas.artists == "Canyon City"].iloc[0].track_id
    katy = linhas[linhas.artists == "Katy Perry"].iloc[0].track_id
    compat_acustica = set(p.moods_compativeis(acustica))
    compat_katy = set(p.moods_compativeis(katy))
    assert compat_acustica != compat_katy, "duas versões com perfis opostos deram os mesmos moods"
    assert "Acustico" in compat_acustica
    assert "Energetico" in compat_katy


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok:", nome)
    print("todos passaram")
