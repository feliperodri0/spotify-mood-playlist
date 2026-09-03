"""Testes do contador de cota (ticket #2).

Isola o arquivo de estado num diretório temporário -- nunca toca
produto/logs/cota_youtube.json de verdade.

Rodar:
    .venv/bin/python produto/tests/test_cota_youtube.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cota_youtube  # noqa: E402


def com_arquivo_temporario(fn):
    """Troca cota_youtube.ARQUIVO por um caminho temporário durante o teste."""
    def envolvida():
        original = cota_youtube.ARQUIVO
        with tempfile.TemporaryDirectory() as tmp:
            cota_youtube.ARQUIVO = Path(tmp) / "cota.json"
            try:
                fn()
            finally:
                cota_youtube.ARQUIVO = original
    envolvida.__name__ = fn.__name__
    return envolvida


@com_arquivo_temporario
def test_estado_inicial_sem_arquivo():
    e = cota_youtube.estado()
    assert e == {
        "usadas": 0, "restantes": 10_000, "limite": 10_000,
        "reseta_em": e["reseta_em"],  # texto fixo, não é o que este teste checa
    }


@com_arquivo_temporario
def test_gastar_acumula():
    cota_youtube.gastar(100)
    cota_youtube.gastar(50)
    assert cota_youtube.estado()["usadas"] == 150
    assert cota_youtube.estado()["restantes"] == 9_850


@com_arquivo_temporario
def test_restantes_nunca_fica_negativo():
    cota_youtube.gastar(15_000)  # mais que o limite diário
    assert cota_youtube.estado()["restantes"] == 0


@com_arquivo_temporario
def test_reseta_quando_a_data_salva_e_de_outro_dia():
    cota_youtube.ARQUIVO.write_text(json.dumps({"data": "2020-01-01", "usadas": 9999}))
    e = cota_youtube.estado()
    assert e["usadas"] == 0, "não resetou ao ler um estado de um dia diferente"
    assert e["restantes"] == 10_000


@com_arquivo_temporario
def test_gastar_apos_dia_antigo_comeca_do_zero():
    cota_youtube.ARQUIVO.write_text(json.dumps({"data": "2020-01-01", "usadas": 9999}))
    cota_youtube.gastar(100)
    assert cota_youtube.estado()["usadas"] == 100, "gastar() somou em cima do estado do dia velho"


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok:", nome)
    print("todos passaram")
