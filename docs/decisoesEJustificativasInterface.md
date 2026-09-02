# Decisões e Justificativas — Fase 4 (Interface)

Este documento registra as decisões de `entregas/interface_playlist.ipynb` (o motor) e do artifact HTML publicado (a interface visual), no mesmo formato dos documentos anteriores.

## Motor (`gerar_playlist`)

**Decisão:** encapsular `selecionar_candidatas` (Fase 2) + `sequenciar` (Fase 3, já com a correção de deduplicação por `(track_name, artists)`) numa única função `gerar_playlist(palavras, n)`.
**Justificativa:** é exatamente a chamada que uma interface real faria a cada pedido do usuário — reunir num só ponto de entrada evita que a lógica de composição fique espalhada/duplicada entre notebook e interface.

## Pré-computação em vez de backend em tempo real

**Decisão:** pré-computar as 92 combinações possíveis de 1 a 3 palavras do vocabulário (`C(8,1)+C(8,2)+C(8,3) = 92`) e exportar como `playlists_precomputadas.json` (276 KB), consumido por uma página estática, em vez de expor a função Python via API/servidor.
**Justificativa:** consistente com a decisão já tomada na avaliação da API do Spotify (`planejamentoModelo.md`) — nada nesta arquitetura depende de contexto de sessão do usuário, então pré-cálculo offline é estritamente melhor que computação sob demanda: sem custo de infraestrutura, sem latência, e o ambiente de execução deste projeto (Claude Code / notebooks) não tem um servidor persistente para expor de qualquer forma.

## Interface visual: mapa de mood em vez de grade de chips

**Decisão:** em vez da grade de 8 botões do mockup original (`planejamentoModelo.md`, Seção 8), a interface publicada posiciona os 8 moods num **plano cartesiano real** de energia (eixo Y) × valência (eixo X), usando as coordenadas exatas das âncoras calibradas na Fase 2 — não uma roda ou grade decorativa.
**Justificativa:** o Circumplex Model of Affect (Russell, 1980) — já citado como base teórica do vocabulário de mood — é literalmente definido nesses dois eixos. Plotar os moods nas coordenadas reais em vez de espaçá-los uniformemente numa grade torna visível uma informação real dos dados (ex: `Energetico`, `Feliz` e `Dancante` têm a mesma energia, diferindo só em valência/danceability) em vez de escondê-la atrás de uma grade genérica.

**Decisão:** ao selecionar 2-3 moods, desenhar uma linha conectando os pontos e um marcador no centroide.
**Justificativa:** o centroide desenhado é literalmente o ponto-alvo que `selecionar_candidatas` calcula (média das âncoras) — a interface não está apenas bonita, está mostrando o mecanismo real de combinação de mood, não uma decoração.

**Decisão:** documentar visualmente a sobreposição de `Calmo`/`Acustico` (mesmo ponto de energia/valência) em vez de escondê-la com um deslocamento silencioso.
**Justificativa:** os dois moods realmente ocupam a mesma posição nesses dois eixos (só diferem em `acousticness`, não plotado) — mover um deles sem explicar seria impreciso; a legenda com linha tracejada é honesta sobre a limitação de um mapa 2D representando um espaço de 6 dimensões.

## Faixas exibidas: BPM e código Camelot, não só nome/artista

**Decisão:** exportar e exibir o código Camelot (`8B`, `5A` etc.) e o BPM de cada faixa, com um indicador de "Δ BPM" entre faixas consecutivas.
**Justificativa:** são exatamente os dois critérios que o sequenciamento (Fase 3) usa para ordenar a playlist — mostrar isso explicitamente permite que quem usa a interface veja *por que* a ordem faz sentido, em vez de receber uma lista sem explicação do mecanismo por trás.

## Quantidade de faixas configurável

**Decisão:** oferecer 5 tamanhos discretos (10/15/20/25/30 faixas), não um campo numérico livre.
**Justificativa:** sem backend em tempo real, cada tamanho precisa estar pré-computado — um campo livre exigiria pré-computar (ou aceitar que não funcione) qualquer valor entre 1 e 113.549. 5 opções cobrem uma faixa razoável de uso (playlist curta a média) com custo de pré-computação pequeno (`92 combinações × 5 tamanhos = 460`, ainda rápido de gerar).

**Erro real encontrado ao testar tamanhos menores:** com o multiplicador fixo `n × 6` (decisão original da Fase 3), 1 das 460 combinações (`Energetico` sozinho, `n=10`) retornava só 9 faixas — o multiplicador fixo não garante candidatas únicas suficientes em regiões do espaço com muita concentração de duplicata. Testado à parte com `n=8` numa combinação diferente, o problema ficou mais grave (48 vizinhos brutos → só 6 únicos).
**Correção:** `selecionar_candidatas` passou a **escalonar** a busca (dobrar o raio) até achar `n` candidatas únicas ou esgotar o catálogo, em vez de um multiplicador fixo torcendo pra dar certo. Corrigido nas 3 cópias da função (Fases 2, 3 e 4) para consistência — confirmado com 0 de 460 combinações abaixo do tamanho pedido após a correção (era 1 antes).

## Links de escuta (YouTube) em vez de playlist salva — na interface

**Decisão:** cada faixa da playlist gerada na interface (artifact) tem um link (`▶`) que abre uma **busca** do YouTube pelo nome da faixa + artista, não uma playlist real criada numa conta.
**Justificativa:** criar uma playlist de verdade, salva numa conta do YouTube, exige autenticação OAuth com uma conta Google real — não há essa credencial neste ambiente, e simular isso seria enganoso. Um link de busca não exige nenhuma autenticação, funciona imediatamente, e é suficiente para o propósito real (Fase 5: alguém consegue ouvir a sequência gerada, faixa a faixa, na ordem certa, e julgar se a transição soa bem).

## Criação de playlist real via OAuth — script à parte (`youtube_playlist_oauth.py`)

**Decisão:** implementar o fluxo OAuth completo (busca de vídeo + criação de playlist + inserção de itens, via `google-api-python-client`) como um **script Python standalone**, não dentro de um notebook executado via `nbconvert`, e não integrado à interface publicada.
**Justificativa:** o consentimento OAuth (`InstalledAppFlow.run_local_server`) precisa abrir um navegador de verdade e receber um redirecionamento HTTP local — isso não funciona num kernel de notebook executado de forma não-interativa (`--execute`), que é como todos os outros notebooks deste projeto são rodados. Também não é algo que a interface web (artifact, roda no navegador do espectador, sem backend) consiga fazer — a etapa de login tem que acontecer no terminal/máquina de quem for gerar a playlist.

**Decisão:** privacidade padrão `unlisted` (não listada), não `private` nem `public`.
**Justificativa:** o caso de uso é compartilhar a playlist com o grupo/colegas para validação por escuta — `private` restringiria a visualização só à conta que criou; `public` a tornaria buscável publicamente sem necessidade. `unlisted` permite compartilhar por link, sem indexação pública.

**Decisão:** documentar explicitamente o custo de cota da API (YouTube Data API v3, 10.000 unidades/dia grátis; ~3.050 unidades por playlist de 20 faixas) e avisar que **não é viável** gerar as 460 combinações pré-computadas da Fase 4 dessa forma.
**Justificativa:** sem esse aviso, seria fácil tentar automatizar a criação de todas as combinações e esbarrar num erro de cota confuso pela metade do processo — o script é para gerar playlists pontuais escolhidas à mão, não para substituir a pré-computação.

**Limitação registrada:** a busca (`search().list`) usa o primeiro resultado do YouTube para "nome da faixa + artista" — não há garantia de que seja a gravação oficial correta (pode vir um cover, lyric video de terceiro, ou não encontrar nada para faixas de catálogo obscuro/internacional). O script reporta explicitamente quais faixas não foram encontradas, em vez de falhar silenciosamente ou inserir o vídeo errado sem aviso.

## Segunda prova de conceito (Spotify) — avaliada e abortada

**Decisão:** escrever `spotify_playlist_oauth.py` (mesmo padrão do YouTube, usando `spotipy`), verificando antes de codificar que a biblioteca instalada (2.26.0) já usa o endpoint atual (`POST /me/playlists`, não o removido em fevereiro/2026) e testando o motor até o ponto da autenticação — mesmo rigor aplicado ao script do YouTube.
**Por que foi abortada:** ao configurar as credenciais no Spotify Developer Dashboard, o usuário encontrou a exigência de conta Spotify Premium para acesso de desenvolvedor. Sem alternativa gratuita, a via foi descartada — o script foi removido do repositório (não deixado como código morto).
**Justificativa de não manter o código mesmo assim:** um script que nunca vai ser executado (por falta de conta Premium) e que ninguém vai manter atualizado contra futuras mudanças de API do Spotify é só uma fonte de confusão futura ("por que isso existe se não funciona?") — melhor documentar a tentativa e a razão do abandono aqui do que deixar um artefato morto no código.

## Reorganização do repositório

**Decisão:** separar `entregas/` (só os 4 notebooks + artefatos que eles geram) de uma pasta nova `produto/` (todo o código de MVP: `motor_playlist.py`, `youtube_playlist_oauth.py`, `credenciais/`, `app_local/`).
**Justificativa:** `entregas/` tinha acumulado duas responsabilidades diferentes — a entrega formal do curso (notebooks) e código de produto (scripts, backend, credenciais) — crescido organicamente ao longo de várias fases sem um ponto de checagem estrutural. Misturar os dois torna mais difícil para alguém (incluindo o próprio usuário, que sinalizou isso) entender rapidamente "o que é a entrega" vs. "o que é exploração adicional". A separação também resolve, de forma incidental, o fato de `credenciais/` estar dentro da pasta que mais frequentemente é aberta/navegada (`entregas/`) — isolá-la em `produto/credenciais/`, ainda com o mesmo `.gitignore`, reduz a chance de alguém arrastar sem querer algo sensível pra outro contexto.

## Redesign visual (marca "soundpark") e limite de faixas por playlist

**Decisão:** redesenhar a interface (produto local e canvas de design) seguindo a tipografia e paleta do logo `soundpark` fornecido pelo usuário — wordmark em `Baloo 2` (arredondada, bold, igual ao logo) + corpo em `Plus Jakarta Sans`, fundo quase-preto e gradiente verde (`--accent-1` a `--accent-3`) reaproveitando o mesmo mapa de mood energia×valência, mas com legenda em linguagem simples nos eixos ("triste ⟷ feliz", "calmo ⟷ energético") em vez de só rótulos abstratos, e substituindo o campo numérico livre por um seletor de tamanho em pills (5/10/15/20/25/30) com leitura ao vivo do custo de cota.
**Justificativa:** o usuário pediu explicitamente para seguir a tipografia do logo e melhorar a usabilidade. Pills grandes são alvos de toque maiores e mais previsíveis que um campo numérico livre (que também exigiria validar client-side o novo limite a cada tecla); expor o custo de cota em tempo real transforma o limite da API de uma regra escondida em informação visível, o que é usabilidade de verdade, não só estética.

**Decisão:** não reaproveitar o selo oficial do Spotify presente no logo original.
**Justificativa:** o produto não usa mais a API do Spotify (abortada — ver seção acima); manter a marca Spotify na interface implicaria uma integração que não existe. O nome, a tipografia e a paleta do `soundpark` foram mantidos; o selo foi removido.

**Decisão:** reduzir o limite máximo de faixas por playlist de 50 (validação antiga do backend, nunca usada por uma interface real) para **30**, com os tamanhos oferecidos (5/10/15/20/25/30) todos abaixo desse teto.
**Justificativa:** o custo de cota já documentado (Passo 5 / seção OAuth acima) é `50 + 150n` unidades (100 de busca + 50 de inserção por faixa, mais 50 fixas de criação), contra uma cota gratuita de 10.000 unidades/dia. Em `n=50`, uma única playlist consumiria 7.550 unidades — 75% da cota diária, sem margem para reprocessar em caso de erro ou gerar uma segunda playlist no mesmo dia. Em `n=30`, o custo cai para 4.550 unidades (~45%), deixando espaço real para múltiplas gerações diárias. `30` não é um número novo: é o maior tamanho já validado nas 460 combinações pré-computadas da Fase 4 (Passo 4), então o teto reusa uma decisão já testada em vez de introduzir um valor sem histórico. Validação replicada no backend (`TAMANHO_MAXIMO` em `produto/app_local/app.py`, aplicado nos dois endpoints), não só no frontend.

## Segunda iteração: grade de cards no lugar do mapa de dispersão

**Decisão:** substituir o mapa de mood (pontos num plano energia×valência, Passo 3) por uma grade de 8 cards clicáveis, um por clima, com ícone próprio e cor derivada da energia/valência real daquele clima (não mais posição no plano).
**Justificativa:** feedback direto do usuário — a seleção por pontos sobrepostos no mapa era pouco intuitiva ("Calmo" e "Acústico" ocupavam exatamente o mesmo ponto, exigindo um deslocamento visual artificial só para os dois ficarem clicáveis separadamente). Cards são alvos de toque muito maiores e sem ambiguidade de sobreposição — não existe "dois cards no mesmo lugar". A honestidade sobre o dado real (o objetivo original do mapa) é preservada de outra forma: a cor de cada card é derivada matematicamente da energia (satura/ilumina) e valência (matiz, de violeta em valência baixa a verde-amarelo em valência alta) reais do vocabulário — "Calmo" e "Acústico" continuam tendo exatamente a mesma cor, porque têm exatamente os mesmos valores; a nota de transparência foi reescrita para essa nova forma ("mesma cor" em vez de "mesmo ponto").

**Decisão:** substituir a linha conectora + marcador de centroide do mapa por duas barras de energia/valência ("gauge") que mostram a média dos climas selecionados, animadas ao trocar a seleção.
**Justificativa:** mesmo objetivo do centroide original (mostrar o alvo real que `selecionar_candidatas` calcula, não uma decoração) mas em um formato que não depende de o usuário saber ler um plano cartesiano — duas barras rotuladas "Energia" e "Valência" comunicam a mesma informação de forma direta.

**Decisão:** incorporar a imagem do logo `soundpark` (ícone + wordmark + tagline, cortada para remover o selo do Spotify) diretamente como a marca do cabeçalho, em vez de recriar o texto estilizado via CSS.
**Justificativa:** pedido explícito do usuário ("SEGUINDO a tipografia do logo.jpeg e também UTILIZANDO-A"). O selo do Spotify foi removido no corte (`logo-icon.jpg`) pelo mesmo motivo já registrado acima: o produto não integra com o Spotify.

**Decisão:** toda a movimentação (entrada escalonada dos cards, hover/seleção com easing, barras animadas, linhas de resultado surgindo em sequência, glow ambiente sutil no cabeçalho) foi implementada com CSS puro (`@keyframes`/`transition`), sem biblioteca de animação externa (GSAP, anime.js etc.).
**Justificativa:** o canvas de design (`/design`) roda numa iframe sandboxed sem acesso a rede além da própria origem e do Google Fonts — nenhum CDN de JS funcionaria ali. Para manter os dois lugares (canvas e produto local) com o mesmo comportamento e não introduzir uma dependência externa desnecessária num protótipo local offline-first, a mesma abordagem (CSS puro) foi usada nos dois — suficiente para hover, entrada escalonada e transições suaves sem o custo de uma biblioteca.

## Terceira iteração: disco de vinil giratório (three.js) no cabeçalho

**Decisão:** adicionar um disco de vinil 3D giratório (WebGL, via `three.js`) como peça decorativa no cabeçalho do produto local, inspirado numa referência visual de UI de toca-discos ("vinylist") fornecida pelo usuário, com cores adaptadas à identidade `soundpark` (label central em gradiente verde da marca, luz de aro esverdeada, em vez da paleta preto/creme da referência).
**Justificativa:** pedido explícito do usuário para usar um plugin de three.js/WebGL e a imagem de referência como inspiração. É puramente decorativo (não afeta nenhuma funcionalidade real) — implementado com fallback silencioso (`try/catch`) caso o WebGL não esteja disponível no navegador, para não quebrar o resto da página nesse caso.

**Decisão:** `three.js` carregado via CDN (`cdnjs`, versão `0.160.1`, build UMD/global) só no produto local (`produto/app_local/static/index.html`) — não no canvas de design publicado (`/design`), que recebeu em vez disso uma versão em CSS puro (círculo com `repeating-radial-gradient` girando via `@keyframes`).
**Justificativa:** o canvas de design roda numa iframe sandboxed sem acesso a rede além da própria origem e do Google Fonts (mesma restrição já registrada na iteração anterior) — nenhum CDN de JS funciona ali, então `three.js` de verdade é fisicamente impossível de carregar nesse ambiente. O produto local é uma página estática comum servida pelo Flask, aberta num navegador de verdade, sem essa restrição.

**Decisão:** `0.160.1` é a versão mais recente do `three.js` que a `cdnjs` ainda publica como `three.min.js` (build UMD/global, importável por `<script src>` simples). Versões mais novas (r160+) só distribuem módulos ES, que exigiriam um bundler ou `<script type="module">` com import maps — fora do escopo de uma página estática sem etapa de build.
**Justificativa:** o produto inteiro é deliberadamente "sem bundler" (HTML/CSS/JS direto, servido por Flask) — trocar isso só para acomodar uma peça decorativa não se justifica; fixar a versão no teto do que a build UMD oferece preserva essa simplicidade.

## Bug real: cards de clima invisíveis (animação de entrada frágil)

**O que quebrava:** os 8 cards de mood usavam `opacity:0` como estado-base + uma `@keyframes` com `animation-delay` diferente por card + `animation-fill-mode: forwards` pra revelar cada um. Na prática, só o primeiro card (delay 0) chegava a ficar visível de forma confiável — os outros 7 ficavam presos no estado inicial (`opacity:0`), deixando o painel "Escolha o clima" parecendo quase vazio. Confirmado com um teste isolado mínimo (3 `<div>`s com o mesmo padrão, fora do app) reproduzindo o mesmo problema, e com uma captura de tela real da página.
**Correção:** o mesmo efeito (entrada escalonada) reimplementado com um padrão mais robusto — os elementos entram com `opacity:0` só via CSS `transition` (não `@keyframes`), e uma classe `shown` é adicionada por JavaScript (`setTimeout` escalonado por índice) depois da inserção no DOM, em vez de depender de `animation-delay` + `forwards` segurar o estado final. Aplicado nos cards de clima e nas linhas da playlist gerada, nos dois lugares (produto local e canvas de design). A animação de entrada do logo (`rise`) foi removida por não agregar o suficiente para justificar o mesmo risco.
**Justificativa da correção:** `transition` acionada por mudança de classe é o padrão consolidado pra esse tipo de revelação — não depende da máquina de `@keyframes`/`animation-delay` segurar corretamente um estado final, que é exatamente onde o bug apareceu.

## Ajuste de iluminação do disco de vinil (three.js)

**O que estava ruim:** a primeira versão do disco de vinil (Passo 12) usava luzes fracas e um material quase preto — o disco ficava pouco legível contra o fundo quase-preto do cabeçalho (a borda se perdia, o disco parecia "sumir").
**Correção:** luz ambiente e as duas luzes direcionais (key + rim verde) tiveram a intensidade praticamente dobrada; o material do disco foi clareado (de `#0a0a0a` pra `#1c211f`); e a textura procedural dos sulcos ganhou um aro claro na borda externa, que é o que realmente define o contorno do disco contra o fundo escuro.

## Quarta iteração: three.js e GSAP de verdade no canvas de design (plugins instalados)

**Decisão:** com os plugins `threejs-webgl`, `gsap-scrolltrigger` e `react-three-fiber` instalados pelo usuário, o disco de vinil do canvas de design deixou de ser um substituto em CSS e passou a ser WebGL de verdade (`three.js` r128), maior e mais central na composição — e a seleção de clima ganhou um pequeno "bounce" via `GSAP` ao clicar.
**Justificativa:** o sandbox do canvas de design não tem acesso a CDN (só à própria origem e ao Google Fonts) — então as duas bibliotecas foram baixadas e embutidas *inline* no próprio arquivo `.dc.html` (não referenciadas por `<script src="cdn...">`), o que funciona porque nenhuma delas depende de rede para renderizar (WebGL e manipulação de estilo via JS são APIs locais do navegador). `react-three-fiber` não foi usado: ele não tem um build UMD/global utilizável sem bundler, e embuti-lo exigiria também React, ReactDOM e um transpilador de JSX (Babel standalone, ~2-3 MB) inline — inviável dentro do orçamento de um único `.dc.html` e desproporcional a uma peça decorativa.

**Bug real encontrado e evitado: `GSAP` com entrada `.from()` escalonada por card não é confiável sob teste headless com tempo virtual.** Ao usar `gsap.from(el, {..., delay: i*0.05})` para animar a entrada dos 8 cards de clima, só os 3 primeiros chegavam a aparecer, mesmo aumentando o tempo de espera do teste de 4s para 12s (achado confirmado via captura de tela repetida, com o DOM mostrando os 8 elementos presentes e corretos — o problema era só de pintura/renderização, não de lógica). A causa raiz mais provável: o *ticker* do GSAP é baseado em `requestAnimationFrame`, e o modo de "tempo virtual" do Chrome headless (usado para testar sem esperar tempo real) não avança `requestAnimationFrame` de forma confiável — diferente de `setTimeout`, que é exatamente o que esse modo foi feito para adiantar de forma determinística.
**Correção:** a entrada dos cards de clima e das linhas de resultado voltou a usar o padrão já validado (`setTimeout` + `classList.add` + CSS `transition`, sem `@keyframes`/`animation-delay`) — comprovadamente confiável nesse ambiente de teste. O `GSAP` foi mantido só onde o risco de "travar no estado inicial" é inofensivo: o bounce de seleção ao clicar (dispara na hora, por interação real do usuário, sem delay escalonado, e mesmo travado a pior consequência é não voltar da escala 1.06 — nunca ficar invisível).
**Por que registrar isso:** é um lembrete concreto de que uma biblioteca de animação (aqui, especificamente o *ticker* baseado em rAF) pode se comportar de forma diferente sob teste automatizado headless do que em um navegador real — o critério usado para decidir onde confiar nela foi "o que acontece se a animação nunca avançar": para conteúdo que precisa aparecer (cards, resultados), isso é inaceitável; para um microfeedback de clique, é irrelevante.

## O que foi deixado de fora, deliberadamente

**Decisão:** não incluir os controles secundários do mockup original (duração da playlist, faixa-semente inicial, alternância variedade/previsibilidade).
**Justificativa:** nenhum desses mecanismos foi implementado no motor (`gerar_playlist` não aceita esses parâmetros) — incluir os controles na interface sem funcionalidade real por trás seria enganoso. Ficam registrados como escopo futuro, não como decoração.
