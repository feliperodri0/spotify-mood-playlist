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

## Passo 10 — Redesign visual ("soundpark") + limite de faixas revisado

A partir do logo `soundpark` fornecido pelo usuário (tipografia `Baloo 2` arredondada + paleta preto/verde-gradiente), a interface do produto local (`produto/app_local/static/index.html`) e um canvas de design (`/design`) foram redesenhados: mesmo mapa de mood energia×valência (Passo 3), agora com legenda em linguagem simples nos eixos, seletor de tamanho em pills (em vez de campo numérico livre) com leitura ao vivo do custo de cota da API, e a marca/selo do Spotify do logo original substituídos (o produto usa YouTube, não Spotify — ver Passo 8).

Limite máximo de faixas por playlist reduzido de 50 (nunca usado por uma interface real) para **30**, com base no custo de cota já documentado (`50 + 150n` unidades): em `n=50` uma única playlist consumiria 75% da cota diária gratuita (10.000 unid.); em `n=30`, ~45%, deixando margem para mais de uma geração por dia. `30` reaproveita o maior tamanho já validado nas 460 combinações pré-computadas da Fase 4, em vez de introduzir um número sem histórico. Validado nos dois endpoints do backend (`TAMANHO_MAXIMO` em `app.py`), não só no frontend. Testado de novo depois da mudança: servidor local subido, `/api/vocabulario` e `/api/preview` checados via `curl` (incluindo o caso `n=31`, que agora retorna erro), servidor derrubado ao final. Decisões completas em `decisoesEJustificativasInterface.md`.

**Canvas de design publicado:** https://claude.ai/code/artifact/b9077387-f7ec-4a8d-813b-b448c8cd8f66 (protótipo clicável com dados de exemplo — o canvas roda isolado, sem acesso ao backend local; o produto real usa o mesmo visual com o catálogo completo).

## Passo 11 — Segunda iteração: grade de cards, logo incorporado, mais movimento

Feedback do usuário sobre o Passo 10: a seleção de clima por pontos no mapa energia×valência era pouco intuitiva, com círculos sobrepostos (`Calmo`/`Acústico` no mesmo ponto). Substituído por uma grade de 8 cards clicáveis (ícone próprio por clima + cor derivada matematicamente da energia/valência real, não mais posição) e duas barras animadas de energia/valência no lugar do centroide do mapa. O logo `soundpark` passou a ser usado como imagem de verdade no cabeçalho (recortado para remover o selo do Spotify, que não se aplica — produto usa YouTube). Adicionada movimentação em CSS puro (sem biblioteca externa, já que o canvas de design roda sandboxed sem acesso a CDN): entrada escalonada dos cards, hover/seleção com easing, barras animadas, linhas de resultado surgindo em sequência. Decisões completas em `decisoesEJustificativasInterface.md`.

Aplicado nos dois lugares: canvas de design (republicado na mesma URL acima) e produto local (`produto/app_local/static/index.html` + `logo-icon.jpg`). Testado de novo depois da mudança: servidor local subido, `/`, `/logo-icon.jpg`, `/api/vocabulario` e `/api/preview` checados via `curl`, servidor derrubado ao final.

## Passo 12 — Disco de vinil 3D (three.js) no cabeçalho do produto local

Pedido do usuário: usar um plugin de three.js/WebGL, seguindo a tipografia do logo e uma imagem de referência de UI de toca-discos ("vinylist") como inspiração. Um disco de vinil giratório em 3D (textura de sulcos e label procedurais, sem assets externos; braço/tonearm estático apoiado perto da borda; iluminação de estúdio com aro esverdeado) foi adicionado ao cabeçalho de `produto/app_local/static/index.html`, via `three.js` `0.160.1` (CDN `cdnjs`, build UMD — a última versão antes de o `three.js` passar a exigir módulos ES). É puramente decorativo, com fallback silencioso se o WebGL não estiver disponível.

O canvas de design (`/design`) recebeu, em vez disso, uma versão em CSS puro do mesmo disco — o canvas roda sandboxed, sem acesso a CDN, então `three.js` de verdade não roda ali (mesma restrição do Passo 11).

Verificado: HTML com tags balanceadas, URL do CDN respondendo (200), servidor local respondendo em `/`, `/logo-icon.jpg` e `/api/preview` com o arquivo já atualizado. Decisões completas em `decisoesEJustificativasInterface.md`.

## Passo 13 — three.js e GSAP de verdade no canvas (plugins instalados)

Com `threejs-webgl`, `gsap-scrolltrigger` e `react-three-fiber` instalados, o disco de vinil do canvas de design passou de substituto em CSS para WebGL de verdade (`three.js` r128), maior e mais central, e a seleção de clima ganhou um bounce via `GSAP` — as duas libs baixadas e embutidas *inline* no `.dc.html`, já que o sandbox do canvas não acessa CDN. `react-three-fiber` não foi usado (sem build utilizável sem bundler/JSX). Note-se que o front-end local (`produto/app_local/`) foi removido a pedido do usuário nesta mesma sessão — esta iteração ficou só no canvas de design, sem porte para o produto.

Bug real encontrado durante a validação: entrada animada dos 8 cards via `gsap.from()` escalonado só mostrava os 3 primeiros de forma confiável em teste headless com tempo virtual (mesmo com bastante tempo de espera) — o DOM confirmava os 8 elementos corretos, então era um problema de renderização, ligado ao *ticker* do GSAP (baseado em `requestAnimationFrame`) não avançar de forma confiável sob esse modo de teste. Corrigido revertendo a entrada dos cards/linhas de resultado para o padrão já validado (`setTimeout` + `classList` + CSS `transition`), mantendo `GSAP` só no bounce de seleção (disparado por clique real, sem risco de ficar preso invisível). Decisões completas em `decisoesEJustificativasInterface.md`.

**Canvas de design republicado (link novo — o anterior foi excluído):** https://claude.ai/code/artifact/f735afee-1ee0-486b-b389-51a6406cf61e

## Passo 14 — Reestruturação real do topo (masthead + hero)

Feedback direto do usuário sobre o Passo 13: a logo parecia "colada" (destacada do resto do visual) e o resultado geral parecia repetir o que já tinha sido feito antes. Causa raiz da logo: a imagem retangular (`logo-icon.jpg`) tinha fundo preto próprio — mesmo com cores parecidas, a borda do JPEG criava uma "caixa" visível sobre o fundo da página.

Correção, não incremental desta vez: o wordmark "soundpark" passou a ser texto nativo em HTML/CSS (mesma tipografia, `Baloo 2`), e o ícone foi recortado da logo original com fundo removido de verdade (matte por luminância + filtro de mediana pra tirar ruído de compressão JPEG nas bordas, `icon-mark.png`, 25 KB) — sem caixa, sem borda visível. O topo foi dividido em dois blocos com ritmos diferentes: um masthead estreito (ícone + wordmark compactos à esquerda, status à direita, como um cabeçalho de app de verdade) e, abaixo, um hero centralizado com o disco de vinil grande e um headline (a própria tagline da marca, em escala maior) — em vez do padrão de "logo de um lado, vinil do outro" repetido nas três iterações anteriores.

Verificado via captura de tela (topo) e leitura do DOM (grade de clima, para confirmar que a classe `shown` continua sendo aplicada corretamente nos 8 cards — a tela às vezes captura um quadro intermediário da transição de opacidade, mas o estado real está sempre correto).

**Canvas de design republicado (mesmo link do Passo 13):** https://claude.ai/code/artifact/f735afee-1ee0-486b-b389-51a6406cf61e

## Passo 15 — Porte para o produto local

A versão reestruturada do Passo 14 (masthead + hero, ícone com fundo transparente, wordmark nativo, sem a etiqueta de status no topo) foi portada para `produto/app_local/static/index.html`, agora com dados reais (não mais faixas de exemplo): `/api/vocabulario` ao vivo alimenta a cor de cada card, `/api/preview` e `/api/criar-youtube` funcionam como antes. `three.js` e `GSAP` carregados via CDN (não embutidos inline, diferente do canvas) — esta página roda num navegador de verdade, sem a restrição de sandbox. A etiqueta de status ("Produto local · YouTube conectado") foi mantida aqui (diferente do canvas, onde foi removida) porque é informação real sobre o estado da conexão, não um rótulo de protótipo. Ícone (`icon-mark.png`) copiado para `produto/app_local/static/`. Testado com o servidor já em execução: `/`, `/icon-mark.png`, `/api/vocabulario` e `/api/preview` via `curl`, e captura de tela confirmando os 8 cards, o vinil e o wordmark renderizando corretamente com dados reais.

## Estado atual

Fases 1-4 implementadas, documentadas, e com uma prova de conceito de produto funcional (YouTube), com interface redesenhada (Passo 10). Falta apenas a Fase 5 (Avaliação qualitativa por escuta humana) — nenhuma métrica das fases anteriores substitui isso.
