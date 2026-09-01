# Semana 2 — Spotify Tracks Dataset (Projeto CBL)

Projeto CBL (Challenge Based Learning) da Residência em TIC — Sistemas de Machine Learning. Pipeline completo, do EDA até um protótipo de interface, para gerar playlists por mood com transições suaves a partir do [Spotify Tracks Dataset](dataset.csv) (113.549 faixas após limpeza).

## Estrutura

```
├── dataset.csv                  # dataset bruto (Spotify Tracks Dataset)
├── dados_externos/
│   └── mtg_jamendo/              # calibração externa (MTG-Jamendo) — ver docs/roteiroModelo.md
├── entregas/                     # notebooks e artefatos gerados (o pipeline em si)
│   ├── eda_spotify.ipynb
│   ├── modelo_mood_clustering.ipynb
│   ├── sequenciamento_playlist.ipynb
│   ├── interface_playlist.ipynb
│   ├── youtube_playlist_oauth.py
│   └── credenciais/               # (gitignored) client_secret.json / token.json do OAuth
├── docs/                         # todo o raciocínio: planejamento, decisões, roteiros
└── materiais_aula/                # slides e guia originais fornecidos no curso
```

## Ordem de leitura recomendada

1. [`docs/resumoChatCBL.md`](docs/resumoChatCBL.md) — brainstorming inicial e decisão de escopo.
2. [`docs/guidingQuestions.md`](docs/guidingQuestions.md) — guiding questions, classificadas e respondidas.
3. [`entregas/eda_spotify.ipynb`](entregas/eda_spotify.ipynb) — EDA completo (`docs/roteiroEDA.md` / `docs/decisoesEJustificativasEDA.md`).
4. [`docs/planejamentoModelo.md`](docs/planejamentoModelo.md) — plano do modelo (vocabulário de mood, clustering, sequenciamento, interface).
5. Notebooks de implementação, na ordem: `modelo_mood_clustering.ipynb` → `sequenciamento_playlist.ipynb` → `interface_playlist.ipynb` — cada fase com seu par `roteiro*.md` / `decisoesEJustificativas*.md` em `docs/`.

## Rodando localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib seaborn scikit-learn jupyter nbformat scipy joblib
jupyter notebook entregas/
```

Para o script de criação de playlist real no YouTube (`entregas/youtube_playlist_oauth.py`), veja o passo a passo de configuração de credenciais no cabeçalho do próprio arquivo.
