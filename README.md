# Semana 2 — Spotify Tracks Dataset (Projeto CBL)

Projeto CBL (Challenge Based Learning) da Residência em TIC — Sistemas de Machine Learning. Pipeline completo, do EDA até um protótipo funcional, para gerar playlists por mood com transições suaves a partir do [Spotify Tracks Dataset](dataset.csv) (113.549 faixas após limpeza).

> **Primeira vez aqui? Leia [`COMECE_AQUI.md`](COMECE_AQUI.md).** Explica o projeto inteiro em linguagem simples, sem precisar atravessar os 13 documentos de `docs/`.

## Estrutura

```
├── dataset.csv                  # dataset bruto (Spotify Tracks Dataset)
├── dados_externos/
│   └── mtg_jamendo/               # calibração externa (MTG-Jamendo) — ver docs/roteiroModelo.md
├── entregas/                     # ENTREGA FORMAL: os 4 notebooks + artefatos que eles geram
│   ├── eda_spotify.ipynb
│   ├── modelo_mood_clustering.ipynb
│   ├── sequenciamento_playlist.ipynb
│   ├── interface_playlist.ipynb
│   └── *.parquet / *.joblib / *.json / *.csv    (artefatos gerados pelos notebooks)
├── produto/                      # MVP de validação, fora do escopo formal da entrega
│   ├── motor_playlist.py          # lógica única de seleção + sequenciamento (usada por tudo abaixo)
│   ├── youtube_playlist_oauth.py  # cria playlist real no YouTube via OAuth
│   ├── credenciais/                (gitignored) client_secret.json / token.json
│   └── app_local/                 # backend Flask + interface web, roda local
├── docs/                         # todo o raciocínio: planejamento, decisões, roteiros
└── materiais_aula/                # (gitignored) slides e guia originais fornecidos no curso
```

## Ordem de leitura recomendada

1. [`docs/resumoChatCBL.md`](docs/resumoChatCBL.md) — brainstorming inicial e decisão de escopo.
2. [`docs/guidingQuestions.md`](docs/guidingQuestions.md) — guiding questions, classificadas e respondidas.
3. [`entregas/eda_spotify.ipynb`](entregas/eda_spotify.ipynb) — EDA completo (`docs/roteiroEDA.md` / `docs/decisoesEJustificativasEDA.md`).
4. [`docs/planejamentoModelo.md`](docs/planejamentoModelo.md) — plano do modelo (vocabulário de mood, clustering, sequenciamento, interface).
5. Notebooks de implementação, na ordem: `modelo_mood_clustering.ipynb` → `sequenciamento_playlist.ipynb` → `interface_playlist.ipynb` — cada fase com seu par `roteiro*.md` / `decisoesEJustificativas*.md` em `docs/`.
6. [`produto/`](produto/) — MVP funcional (validação de conceito): backend + interface local que gera playlists reais no YouTube. Ver `docs/roteiroInterface.md` (Passos 6-7) e `produto/app_local/README.md`.

## Rodando o EDA/modelo localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib seaborn scikit-learn jupyter nbformat scipy joblib
jupyter notebook entregas/
```

## Rodando o produto (MVP)

```bash
cd produto/app_local
../../.venv/bin/python app.py
```
Abra `http://localhost:5001`. Setup de credenciais do YouTube: ver cabeçalho de `produto/youtube_playlist_oauth.py`.

**Nota:** uma segunda prova de conceito com o Spotify (em vez do YouTube) foi avaliada e abortada — a API de desenvolvedor do Spotify exige conta Premium, o que a descartou como opção gratuita para este MVP.
