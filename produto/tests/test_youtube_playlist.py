"""Testes do caminho de criação no YouTube, sem tocar na API.

Existem por causa de um bug real: `playlistItems.insert` era chamado com
`position: i`, o índice na lista completa. Como faixas não encontradas são
puladas, o `i` passava a apontar além do fim da playlist e o YouTube rejeitava
todas as inserções seguintes — uma busca falha derrubava o resto. O sintoma foi
uma playlist de 30 faixas que saiu com 16, sem aviso nenhum.

Rodar:
    .venv/bin/python produto/tests/test_youtube_playlist.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from youtube_playlist_oauth import criar_playlist_youtube  # noqa: E402


class FakeExec:
    def __init__(self, resultado):
        self._r = resultado

    def execute(self):
        return self._r


class FakeYouTube:
    """Registra os corpos enviados, em vez de falar com o YouTube."""

    def __init__(self):
        self.inseridos = []

    def playlists(self):
        return self

    def playlistItems(self):
        return self

    def insert(self, part=None, body=None):
        self.inseridos.append(body)
        # Espelha a regra real do YouTube: position além do fim é inválido.
        pos = body["snippet"].get("position")
        assert pos is None or pos <= len(self.inseridos) - 1, f"position {pos} fora do fim"
        return FakeExec({"id": "item"})


class FakePlaylists(FakeYouTube):
    def insert(self, part=None, body=None):
        if "status" in body:  # criação da playlist
            return FakeExec({"id": "PL_teste"})
        return super().insert(part=part, body=body)


def test_faixa_nao_encontrada_nao_derruba_as_seguintes():
    yt = FakePlaylists()
    ids = ["a", "b", None, "c", "d"]  # a 3ª não foi encontrada
    url, adicionadas, falhas = criar_playlist_youtube(yt, "t", "d", ids)
    assert adicionadas == 4, f"esperava 4 adicionadas, veio {adicionadas}"
    assert falhas == []
    assert url.endswith("PL_teste")


def test_insert_nao_manda_position():
    yt = FakePlaylists()
    criar_playlist_youtube(yt, "t", "d", ["a", None, "b"])
    itens = [b for b in yt.inseridos if "status" not in b]
    assert all("position" not in b["snippet"] for b in itens), "position voltou a ser enviado"


def test_conta_o_total_pedido_e_nao_o_adicionado():
    yt = FakePlaylists()
    _, adicionadas, _ = criar_playlist_youtube(yt, "t", "d", [None, None, "a"])
    assert (adicionadas, 3) == (1, 3), "o chamador precisa saber 1 de 3"


if __name__ == "__main__":
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok:", nome)
    print("todos passaram")
