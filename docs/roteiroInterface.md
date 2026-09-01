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

Estender pra 5 tamanhos (`92 × 5 = 460` playlists) expôs um bug real: com o multiplicador fixo da Fase 3 (`n × 6`), 1 combinação (`Energetico`, `n=10`) retornava menos faixas que o pedido. Corrigido com busca escalonada (dobra o raio até achar candidatas únicas suficientes) nas 3 cópias de `selecionar_candidatas` (Fases 2, 3, 4). Confirmado: 0 de 460 combinações com falta, após a correção. Links de busca no YouTube adicionados por faixa (`urllib.parse.quote_plus`, sem API/autenticação). Decisões completas em `decisoesEJustificativasInterface.md`.

## Passo 5 — Playlist real no YouTube via OAuth (`entregas/youtube_playlist_oauth.py`)

Script standalone (não roda via `nbconvert` — precisa abrir navegador de verdade para o consentimento OAuth). Reaproveita o motor da Fase 4, resolve cada faixa para um vídeo real via `search().list`, cria a playlist (`playlists().insert`) e adiciona as faixas na ordem sequenciada (`playlistItems().insert`), devolvendo a URL compartilhável (`youtube.com/playlist?list=...`).

**Testado (sem credencial real):** a geração da playlist (seleção de candidatas + sequenciamento) roda corretamente até o ponto exato da autenticação — confirmado com um teste que substitui a etapa de login por um erro proposital, validando que tudo antes dela funciona. A etapa de login/consentimento em si só pode ser feita por quem for rodar o script, na própria máquina — não é algo automatizável a partir daqui.

**Requer, do lado de quem for rodar:** um projeto no Google Cloud Console com a YouTube Data API v3 ativada e credenciais OAuth (`client_secret.json`) — passo a passo completo no cabeçalho do próprio script. Decisões e limitações registradas em `decisoesEJustificativasInterface.md`.

## Estado atual

Fases 1-4 implementadas e documentadas. Falta apenas a Fase 5 (Avaliação qualitativa por escuta humana) — nenhuma métrica das fases anteriores substitui isso.
