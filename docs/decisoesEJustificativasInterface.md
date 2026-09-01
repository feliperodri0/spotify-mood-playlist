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

## O que foi deixado de fora, deliberadamente

**Decisão:** não incluir os controles secundários do mockup original (duração da playlist, faixa-semente inicial, alternância variedade/previsibilidade).
**Justificativa:** nenhum desses mecanismos foi implementado no motor (`gerar_playlist` não aceita esses parâmetros) — incluir os controles na interface sem funcionalidade real por trás seria enganoso. Ficam registrados como escopo futuro, não como decoração.
