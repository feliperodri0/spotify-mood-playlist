# Produto local — Constelação de Mood

MVP rodando 100% na sua máquina (não publicado como artifact) — backend Flask + a mesma interface visual da Fase 4, agora falando com um servidor de verdade em vez de dados pré-computados.

## Rodar

```bash
cd produto/app_local
../../.venv/bin/python app.py
```

Abra **http://localhost:5001** no navegador.

## O que os dois botões fazem

- **"Pré-visualizar (grátis)"** — gera a playlist ao vivo (Fases 2-3), sem tocar a API do YouTube. Pode clicar quantas vezes quiser.
- **"Criar playlist de verdade no YouTube"** — usa o login já autenticado (`produto/credenciais/token.json`) pra resolver cada faixa e criar a playlist real. **Gasta cota da API** (~100 unidades por faixa buscada + 50 por faixa adicionada) — use com moderação.

## Pré-requisito

O login OAuth já precisa ter sido feito uma vez (`produto/youtube_playlist_oauth.py`, ou o próprio botão "Criar no YouTube" aciona o mesmo fluxo se `token.json` ainda não existir — nesse caso abre o navegador pedindo consentimento).
