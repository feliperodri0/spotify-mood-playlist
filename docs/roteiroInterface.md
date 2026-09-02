# Roteiro da Fase 4 — Interface

Documento de acompanhamento de `entregas/interface_playlist.ipynb` (motor) e do artifact HTML publicado (interface visual), implementando a Seção 8 de `planejamentoModelo.md`. Justificativas em `decisoesEJustificativasInterface.md`.

## Passo 1 — Motor (`gerar_playlist`)

Reaproveita, sem duplicar, as funções já validadas: Camelot Wheel e `selecionar_candidatas` (Fase 2/3) + `sequenciar` (Fase 3). `gerar_playlist(palavras, n)` combina as duas numa única chamada.

## Passo 2 — Pré-computação

92 combinações de 1 a 3 palavras do vocabulário de 8 moods geradas e exportadas em `entregas/playlists_precomputadas.json` (276 KB — inclui `track_name`, `artists`, `tempo`, `track_genre`, `mood`, `camelot` por faixa).

## Passo 3 — Interface visual

Artifact HTML publicado, consumindo o JSON pré-computado (sem backend em tempo real):
- Mapa de mood: os 8 pontos posicionados nas coordenadas reais de energia/valência das âncoras (não uma grade genérica) — clicáveis, até 3 selecionáveis, com linha conectora e marcador de centroide (o ponto-alvo real do algoritmo).
- Seletor de tamanho: 10/15/20/25/30 faixas.
- Ao gerar: lista de faixas estilo track browser, com selo de BPM e código Camelot por faixa, indicador de Δ BPM entre faixas consecutivas (visualizando os dois critérios reais do sequenciamento, Fase 3), e um link `▶` por faixa que abre uma busca no YouTube — para validação por escuta (Fase 5), sem criar playlist real (exigiria OAuth que este protótipo não tem).
- Rodapé explicitando que é um protótipo pré-computado, com link de volta pra documentação.

**Publicado em:** https://claude.ai/code/artifact/5b12e6f2-b61a-4332-9545-cf0638572400

## Passo 4 — Correção: quantidade configurável + bug de deduplicação

Estender pra 5 tamanhos (`92 × 5 = 460` playlists) expôs um bug real: com o multiplicador fixo da Fase 3 (`n × 6`), 1 combinação (`Energetico`, `n=10`) retornava menos faixas que o pedido. Corrigido com busca escalonada (dobra o raio até achar candidatas únicas suficientes) — na época, replicado manualmente em 3 cópias da função (ver Passo 7, onde isso deixou de ser necessário). Confirmado: 0 de 460 combinações com falta, após a correção. Links de busca no YouTube adicionados por faixa (`urllib.parse.quote_plus`, sem API/autenticação). Decisões completas em `decisoesEJustificativasInterface.md`.

## Passo 5 — Playlist real no YouTube via OAuth (`produto/youtube_playlist_oauth.py`)

Script standalone (não roda via `nbconvert` — precisa abrir navegador de verdade para o consentimento OAuth). Reaproveita o motor, resolve cada faixa para um vídeo real via `search().list`, cria a playlist (`playlists().insert`) e adiciona as faixas na ordem sequenciada (`playlistItems().insert`), devolvendo a URL compartilhável (`youtube.com/playlist?list=...`).

**Testado (sem credencial real):** a geração da playlist roda corretamente até o ponto exato da autenticação — confirmado com um teste que substitui a etapa de login por um erro proposital. **Testado com credencial real, depois:** login confirmado funcionando via `youtube.channels().list(mine=True)`.

**Dois erros reais de configuração, encontrados e corrigidos durante o setup:**
1. `redirect_uri_mismatch` — a biblioteca usa `localhost` por padrão no redirecionamento; a isenção do Google de não exigir URI pré-cadastrada vale para o IP literal `127.0.0.1`, não a string `localhost`. Corrigido forçando `host="127.0.0.1"` explicitamente.
2. `Erro 403: access_denied` — app em modo "Teste" no Google Cloud Console exige que a conta usada esteja cadastrada como "usuário de teste" na tela de consentimento OAuth. Resolvido adicionando o e-mail correspondente.

**Requer, do lado de quem for rodar:** um projeto no Google Cloud Console com a YouTube Data API v3 ativada e credenciais OAuth (`client_secret.json`) — passo a passo completo no cabeçalho do próprio script. Decisões e limitações registradas em `decisoesEJustificativasInterface.md`.

## Passo 6 — Produto local (`produto/app_local/`)

Pivô de escopo: como o objetivo é validação de conceito (não lançamento), o backend em nuvem (Vercel) cogitado para escalar além de 5 usuários OAuth deixou de ser necessário. Em vez disso: backend Flask **local**, servindo a mesma interface visual, com dois endpoints reais — `/api/preview` (gera a playlist ao vivo, grátis) e `/api/criar-youtube` (cria a playlist de verdade, usando o login OAuth já autenticado em `produto/credenciais/token.json`).

Backend testado (`/api/vocabulario`, `/api/preview`) antes de entregar — servidor subido, endpoints chamados via `curl`, resultado conferido, servidor derrubado (não deixado rodando sem o usuário saber). Passo a passo de uso em `produto/app_local/README.md`.

## Passo 7 — Refatoração: motor único (`produto/motor_playlist.py`)

A lógica de seleção de candidatas + sequenciamento estava copiada em 3 lugares diferentes — o que já tinha causado o bug do Passo 4 (a correção precisou ser replicada manualmente). Extraída para um módulo único (classe `PipelineMood`), testado isoladamente (resultado idêntico ao anterior, checagem de consistência 100%) antes de qualquer script depender dele. `youtube_playlist_oauth.py` e `app_local/app.py` atualizados para importar do módulo — testados de novo depois, sem quebrar nada.

## Passo 8 — Segunda prova de conceito: Spotify — avaliada e abortada

Um script análogo ao do YouTube (`spotipy` + OAuth) chegou a ser escrito e testado até o ponto da autenticação (mesmo padrão de teste dos passos anteriores) — confirmado, antes de escrever código, que a biblioteca `spotipy` 2.26.0 já usa o endpoint atual (`POST /me/playlists`) e que seu fluxo de OAuth pede colagem manual da URL de redirecionamento (diferente do Google, que abre servidor local automático).

**Abortado:** o acesso de desenvolvedor ao Spotify Web API exige conta Spotify Premium, informado pelo usuário ao tentar configurar. Sem alternativa gratuita nessa via — descartado como opção de prova de conceito. Script removido do repositório.

## Passo 9 — Reorganização do repositório

`entregas/` havia acumulado duas coisas diferentes: os 4 notebooks (entrega formal do curso) e o código de produto (motor, script do YouTube, backend local, credenciais). Separado em duas pastas: `entregas/` mantém só os notebooks e os artefatos que eles geram; `produto/` recebeu `motor_playlist.py`, `youtube_playlist_oauth.py`, `credenciais/` e `app_local/`. Caminhos internos corrigidos (`ENTREGAS_DIR` explícito nos scripts que agora vivem fora de `entregas/`) e testados de novo depois da mudança — mesma checagem de sempre: motor rodando até o ponto certo, backend respondendo via `curl` numa porta de teste, sem derrubar a instância que já estava rodando na sessão do usuário. Removido também `entregas/env/` (venv duplicado, 649 MB, nunca versionado) e o script do Spotify abortado.

## Estado atual

Fases 1-4 implementadas, documentadas, e com uma prova de conceito de produto funcional (YouTube). Falta apenas a Fase 5 (Avaliação qualitativa por escuta humana) — nenhuma métrica das fases anteriores substitui isso.
