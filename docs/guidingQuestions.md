# Guiding Questions — Spotify Tracks Dataset

Versão refinada e priorizada das guiding questions levantadas na fase inicial do CBL (ver histórico completo do brainstorming em [`resumoChatCBL.md`](./resumoChatCBL.md)). Cada pergunta está classificada por categoria e por prioridade de tratamento.

**Legenda de prioridade:**
- `responder já` — tratada durante o Investigate (EDA), com achado registrado.
- `planejar` — depende de decisão de modelagem ainda não tomada; não é respondida no EDA, mas orienta a fase Act.
- `se sobrar tempo` — relevante, mas não bloqueia a decisão de modelagem; retomar se houver tempo disponível.
- `cortar sem dó` — descartada; não será respondida.

## Dados

- **O que significa cada coluna?** *(responder já)*

  **Resposta:** as 20 colunas se agrupam em 4 blocos — identificação (`track_id`, `artists`, `album_name`, `track_name`), variável de negócio (`popularity`), audio features (`danceability`, `energy`, `loudness`, `speechiness`, `acousticness`, `instrumentalness`, `liveness`, `valence`, `tempo`, mais `key`, `mode`, `time_signature` como discretas) e metadados (`duration_ms`, `explicit`, `track_genre`). O dicionário completo, com a definição de cada coluna segundo a fonte oficial (Hugging Face/Kaggle), está documentado no notebook (`entregas/eda_spotify.ipynb`, Passo 1). Dois pontos da documentação exigiram checagem à parte: `key = -1` significa "tonalidade não detectada" (não ocorre neste dataset) e `time_signature` é documentado como variando de 3 a 7, mas o dataset real contém também os valores 0 e 1 (ver Passo 2.4).

- **Os 114 gêneros com exatamente 1.000 registros cada indicam um dataset artificialmente balanceado — isso reflete a distribuição real de streams no Spotify?** *(responder já)*

  **Resposta:** não. Confirmado que o dataset bruto tem **exatamente 1.000 registros para cada um dos 114 gêneros, sem exceção** (desvio-padrão da contagem = 0). Isso é estatisticamente impossível de ocorrer naturalmente a partir de dados reais de streaming — a popularidade por gênero no Spotify é conhecidamente desigual (pop e hip-hop concentram um volume de streams muito maior que gêneros de nicho como `grindcore` ou `iranian`). O padrão de "exatamente 1.000 por categoria, sem nenhuma variação" é evidência direta de amostragem estratificada deliberada na construção do dataset (provavelmente uma busca de 1.000 faixas por gênero via API), não uma fotografia do consumo real. Qualquer análise que use a contagem de gêneros deste dataset como proxy de popularidade real de gênero estaria partindo de uma premissa falsa.

- **Removendo as faixas com popularidade zero, os rankings mudam muito?** *(responder já)*

  **Resposta:** sim, de forma significativa. 14% de todas as faixas do dataset têm `popularity == 0`, mas essa proporção está longe de ser uniforme entre gêneros — `jazz` (68%), `soul` (61%), `country` (59%), `rock` (53%), `alternative` (48%) e `dance` (48%) têm proporções muito acima da média geral. Ao comparar o ranking de gêneros por popularidade mediana **com** e **sem** as faixas de popularidade zero, a correlação de Spearman entre as duas ordens é de apenas **0,73** (longe de 1,0, que indicaria nenhuma mudança). Alguns gêneros saltam de forma extrema: `dance` vai da posição ~107ª de 114 (quase o último) para a **1ª posição**; `soul` vai de ~111ª para 8ª; `alternative` de ~107ª para 6ª. Conclusão: um ranking de popularidade por gênero que inclui as faixas de popularidade zero penaliza injustamente gêneros que, por acaso, têm mais faixas "nunca tocadas"/de catálogo — não porque sua música de fato popular seja menos popular.

- **As 114 `track_genre` do dataset se agrupam de forma natural em "famílias de estilo" (ex: lofi ≈ acoustic/chill, eletrônica ≈ edm/house/techno)? Dá pra mapear os 114 gêneros para um conjunto menor de estilos que faça sentido pro usuário final escolher no chat?** *(responder já)*

  **Resposta:** parcialmente. Clustering hierárquico sobre a média das 9 audio features por gênero (notebook, Passo 5.3) encontra grupos musicalmente coerentes — gêneros brasileiros (`sertanejo`, `pagode`, `samba`) isolados num ramo; metal/punk/rock num grande ramo; eletrônica de pista (`techno`, `house`, `trance`, `chicago-house`) noutro; e um ramo "calmo/instrumental" reunindo `new-age`, `ambient`, `classical`, `guitar`, `disney`, `piano`, `study`, `idm`, `iranian`, `sleep` — o mais próximo de um conceito "lofi" que o dataset tem. Mas a estrutura não é limpa: existe um cluster grande (33 gêneros) que mistura `pop`, `jazz`, `opera`, `blues` e `folk` sem separação clara, e `comedy` fica isolado sozinho. Mapear os 114 gêneros para um punhado de "famílias" é viável como primeira aproximação, mas exigiria validação cuidadosa nos gêneros do cluster heterogêneo, onde o agrupamento automático não reflete bem a intuição musical.

- **Dentro de um mesmo estilo (ex: lofi), as músicas são realmente parecidas em atributos de áudio, ou o gênero rotulado esconde bastante variação interna?** *(responder já)*

  **Resposta:** homogeneização moderada, não forte. Medindo a razão entre o desvio-padrão de cada feature dentro do gênero e o desvio-padrão da mesma feature no dataset inteiro, a mediana (114 gêneros) é **0,73** — em média, um gênero é ~27% menos variado internamente que o dataset como um todo. Gêneros como `party`, `house`, `edm`, `metalcore`, `dance` são bem mais fechados (razão ~0,55). Mas `sleep`, `german`, `iranian`, `piano` e `comedy` têm razão **acima de 1** — são tão ou mais heterogêneos internamente quanto o dataset inteiro, ou seja, o rótulo de gênero quase não reduz a incerteza sobre como a faixa realmente soa nesses casos.

- **Duas músicas de gêneros diferentes mas com atributos de áudio muito próximos (ex: uma "acoustic" e uma "chill") deveriam ser recomendadas juntas mesmo com rótulos diferentes?** *(responder já — com ressalva)*

  **Resposta:** o EDA fornece evidência a favor, mas essa é, no fundo, uma decisão de produto, não algo que os dados resolvem sozinhos. A evidência: o cluster heterogêneo de 33 gêneros (achado acima) mostra que gêneros com rótulos bem diferentes entre si (`pop`, `jazz`, `folk`) podem ter perfis de áudio parecidos — ou seja, similaridade sonora cruzando fronteira de gênero é um padrão real nos dados, não hipotético. Isso dá base para segmentar por áudio em vez de (ou além de) gênero. Mas "deveria" recomendar assim é uma escolha de design que depende do que o usuário espera (ver pergunta equivalente na seção Usuário) — os dados mostram que é **possível e sustentado por evidência**, não que seja automaticamente a decisão certa.

- **Os ~24 mil `track_id` duplicados entre gêneros — quando uma faixa aparece em mais de um gênero, isso ajuda ou atrapalha a recomendação por estilo (ela "pertence" a dois estilos ao mesmo tempo)?** *(responder já)*

  **Resposta:** ajuda mais do que atrapalha. Os 15 pares de gênero que mais co-ocorrem na mesma faixa (notebook, Passo 5.3) são quase todos musicalmente coerentes: `reggae`+`reggaeton` (804 faixas), `dub`+`dubstep` (727), `punk`+`punk-rock` (628), `edm`+`house` (624), `alt-rock`+`alternative` (592), `indie`+`indie-pop` (579), e toda a família latina interligada (`latin`, `latino`, `reggaeton`, `reggae`). O par mais frequente, `singer-songwriter`+`songwriter` (1.000 ocorrências — a totalidade de um dos dois gêneros), sugere que são rótulos quase sinônimos no catálogo. Não há evidência de combinações arbitrárias/sem sentido nos pares mais comuns — a multi-rotulagem reflete relações reais de subgênero.

- **Popularidade e estilo têm alguma relação enviesada (ex: estilos populares dominando as recomendações e sufocando estilos de nicho como lofi)?** *(responder já)*

  **Resposta:** quadro misto, não um viés uniforme. Como o dataset não tem gênero `lofi`, a checagem usou os gêneros mais próximos (identificados no cluster "calmo/instrumental"): `chill` está entre os **mais populares do dataset inteiro** (5º de 114, popularidade mediana 57); `ambient` e `piano` ficam acima da mediana (16º, mediana 50); `acoustic` também (24º, mediana 47). Mas `sleep` (61º, mediana 35) e `study` (72º, mediana 28) ficam abaixo do meio da tabela. Ou seja: não é que "tudo que soa lofi" seja sufocado por gêneros mainstream — o efeito é específico por subestilo, e gêneros de função mais utilitária/nicho (`study`, `sleep`) performam pior que gêneros de atmosfera mais "mainstream-friendly" (`chill`).

## Usuário

- **Se o objetivo é recomendar músicas, faz mais sentido segmentar por características de áudio do que por gênero?** Se a IA otimiza para "engajamento" ou "retenção", o usuário pode receber músicas que ele não quer ouvir. *(responder já)*

  **Resposta:** os achados do EDA apontam nessa direção. Primeiro, `track_genre` não é uma partição limpa dos dados: 16.299 músicas (de 89.741 faixas únicas) pertencem legitimamente a 2 ou mais gêneros simultaneamente (Passo 2.2) — ou seja, "gênero" já é uma categoria sobreposta, não exclusiva. Segundo, os boxplots por gênero (Passo 5.2) mostram separação clara entre gêneros contrastantes em `energy`/`acousticness`, mas também uma dispersão interna (IQR) considerável dentro de cada gênero — duas músicas do mesmo gênero podem soar bem diferentes entre si. Isso sugere que características de áudio oferecem uma segmentação mais granular e menos ambígua do que o rótulo de gênero para um caso de uso baseado em "som"/atmosfera.

  Sobre o risco de otimizar para engajamento: a matriz de correlação (Passo 5.1) mostrou que `popularity` **não tem relação linear relevante com nenhuma audio feature** (todas abaixo de 0,1 em módulo). Isso indica que popularidade é explicada majoritariamente por fatores fora deste dataset (marketing, fama do artista, posicionamento em playlist, sinais comportamentais). Um sistema que otimizasse diretamente para popularidade/engajamento usando só essas audio features teria pouquíssimo sinal real pra trabalhar — com risco de aprender atalhos espúrios (ex: viés de popularidade, recomendar sempre o que já é popular) em vez de similaridade de conteúdo genuína. Isso reforça a segmentação por conteúdo/áudio como base mais segura do que otimizar diretamente por uma métrica de engajamento fracamente explicada pelos dados disponíveis.

- **Dado que o usuário escolhe uma música inicial, a semelhança de atributos de áudio entre essa música e as demais do mesmo estilo é suficiente para "parecer certo" pro ouvido, ou faltam atributos importantes que o dataset não tem (letra, vocal, instrumentação)?** *(responder já)*

  **Resposta:** faltam, pelo menos parcialmente. As 9 audio features capturam bem dimensões de produção/energia/ritmo (`energy`, `loudness`, `tempo`, `danceability`) e dão proxies indiretos de presença vocal (`speechiness`, `instrumentalness`), mas o dataset **não tem letra, idioma, timbre vocal nem instrumentação identificada** (`acousticness` é uma confiança estatística de "soa acústico", não um detector de instrumento específico como violão vs. piano). Evidência concreta da lacuna: 17 dos 114 gêneros têm nome que sinaliza conteúdo não-inglês ou culturalmente específico (`spanish`, `french`, `german`, `turkish`, `indian`, `iranian`, `mandopop`, `cantopop`, `k-pop`, `j-pop`, `j-rock`, `j-idol`, `j-dance`, `malay`, `swedish`, `british`, `brazil`) — ou seja, o catálogo é multilíngue, mas nenhuma coluna captura idioma ou conteúdo lírico. Reforça isso o achado do Passo 5.1: `popularity` não é explicada linearmente por nenhuma audio feature, sugerindo que o que faz uma música "parecer certa"/funcionar para um ouvinte envolve fatores (letra, contexto cultural, familiaridade) que este dataset não registra. Segmentar só por áudio é um ponto de partida razoável, não uma solução completa.

- **Se o usuário pedir "lofi" mas a música inicial dele for de um estilo bem diferente (ex: rock pesado), o que a recomendação deveria priorizar: o estilo pedido ou a música inicial?** *(planejar)*
- **Quantas opções de estilo faz sentido mostrar no chat sem sobrecarregar o usuário (ex: 5 vs. 15 categorias)?** *(planejar)*
- **Usuários que escolhem o mesmo estilo esperam variedade (descobrir artistas novos) ou previsibilidade (mais do mesmo)? Isso muda como a recomendação deveria ranquear as músicas dentro do estilo escolhido?** *(planejar)*

## Modelo

- **Quais modelos podem ser criados com base nesse dataset?** → Chatbot, Recomendações. *(responder já)*

  **Resposta:** com base no que o dataset efetivamente contém (audio features numéricas, `track_genre`, `popularity`, e metadados textuais limitados a nomes de artista/álbum/faixa):
  - **Diretamente viável:** clustering não-supervisionado sobre as audio features (agrupamento por "som"); classificação supervisionada usando `track_genre` como rótulo (existe rótulo real, e balanceado por construção); recomendação por similaridade de conteúdo (distância entre vetores de audio features).
  - **Não diretamente viável:** prever `popularity` a partir das audio features via regressão simples — a correlação linear encontrada é praticamente nula (Passo 5.1); exigiria métodos não-lineares e, provavelmente, dados externos que este dataset não tem.
  - **Chatbot:** o dataset não contém texto conversacional nem volume de linguagem natural suficiente para treinar um modelo de linguagem por conta própria. Um chatbot só seria viável como uma camada de interface por cima de um dos modelos acima (ex: um LLM que consulta um motor de recomendação/clustering construído sobre este dataset para responder pedidos em linguagem natural) — não como algo treinado diretamente a partir destes dados.

- **Como o Spotify usa esses dados para recomendar suas músicas?** *(planejar)*
- **Recomendação por similaridade de atributos de áudio (KNN / cosine similarity) dentro do estilo escolhido performa melhor que simplesmente filtrar por `track_genre` e ordenar por popularidade?** *(planejar)*
- **Como avaliar "qualidade" de uma recomendação aqui, já que não é mais regressão de popularidade — usar métricas como precision@k contra o próprio gênero rotulado, ou depender de validação qualitativa/humana?** *(planejar)*
- **Faz sentido usar clustering (ex: K-Means) nos atributos de áudio para descobrir "estilos" que não coincidam exatamente com `track_genre`, e comparar com os rótulos originais do dataset?** *(responder já)*

  **Resposta:** faz sentido tentar, mas o resultado (notebook, Passo 5.4) mostra que o K-Means **não recupera bem** os rótulos de gênero ao nível de faixa individual: comparando um K-Means com K=8 contra `track_genre`, o **Adjusted Rand Index é 0,017** (praticamente zero) e o **Normalized Mutual Information é 0,17** (fraco a moderado). A maioria dos clusters mistura dezenas de gêneros sem nenhum dominante (ex: um cluster com 32.722 faixas tem só 2,4% de participação do gênero mais comum). Duas exceções: um cluster dominado por `comedy` (85,2% de pureza — fala tem assinatura acústica muito distinta) e um cluster que reúne majoritariamente a família `new-age`/`sleep`/`classical`/`ambient`/`piano` (a mesma família "calma" do Passo 5.3). Conclusão: clustering por áudio funciona para separar extremos bem distintos, mas não substitui `track_genre` como sistema de categorização geral — os 114 rótulos carregam informação (contexto cultural, artista, produção) que as 9 audio features sozinhas não capturam.

- **Quais atributos de áudio pesam mais para diferenciar estilos como punk vs. lofi vs. eletrônica (ex: `energy` e `acousticness` separam bem, mas `key` e `time_signature` talvez não ajudem nada)?** *(responder já)*

  **Resposta:** confirmado quantitativamente (notebook, Passo 5.4, via η² de ANOVA por gênero). Da mais para a menos discriminativa: `acousticness` (η²=0,49), `energy` (0,45), `instrumentalness` (0,45), `loudness` (0,45), `speechiness` (0,44), `danceability` (0,41) — cada uma sozinha explica 41-49% da variância entre gêneros. `valence` tem poder moderado (0,30). `liveness` e `tempo` são fracas (0,15 e 0,09). **`key` é essencialmente inútil (η²=0,005)** — quase toda sua variação é dentro dos gêneros, não entre eles; `mode` e `time_signature` também contribuem pouco (~0,06-0,07). A intuição da pergunta estava certa: `energy`/`acousticness` carregam a maior parte do sinal; `key`/`time_signature` quase não ajudam.

- **Como o modelo lida com um estilo que tem poucas músicas de alta popularidade no dataset (recomendação fica pobre/repetitiva)?** *(planejar)*

## Produção

- **Com que frequência o modelo precisaria ser retreinado?** *(planejar)*
- **Como a lista de estilos mostrada no chat seria atualizada se novos gêneros/músicas entrarem na base?** *(planejar)*
- **A recomendação precisa rodar em tempo real (resposta instantânea no chat) ou pode ser pré-calculada por estilo?** *(responder já)*

  **Resposta:** pode (e deve) ser pré-calculada. Nem o rótulo de `track_genre` nem a posição de uma faixa no espaço de audio features mudam por sessão de usuário — são propriedades estáticas do catálogo (113.549 faixas, vetores de 9 dimensões), não dependem de contexto em tempo real. Uma matriz de similaridade completa entre todas as faixas seria inviável para calcular sob demanda (113.549² ≈ 12,9 bilhões de pares), mas isso não é necessário: um índice de vizinhos mais próximos por faixa (ou por cluster/estilo) pode ser calculado **uma vez, offline**, e servido por consulta (*lookup*) instantânea no chat. Computação em tempo real só se tornaria necessária se a recomendação passasse a depender de sinais dinâmicos por usuário (histórico de escuta, feedback em sessão) — que não fazem parte deste dataset e seriam uma extensão futura, não um requisito atual.

- **Como medir, depois de lançado, se os usuários estão satisfeitos com as recomendações do estilo escolhido (ex: taxa de "pular música", tempo de escuta)?** *(planejar)*

## Ética

- **Há questões de direitos autorais nos dados das músicas e artistas?** *(se sobrar tempo)*
- **Dados de artistas menores/independentes estão sub-representados nesse dataset de forma que penalize injustamente certos grupos culturais ou geográficos?** *(se sobrar tempo)*
- **Se certos estilos culturais (ex: `j-idol`, `iranian`) têm poucas faixas populares no dataset, o sistema pode acabar recomendando pior pra quem gosta desses estilos — isso é um viés que precisa ser registrado como limitação?** *(planejar)*
- **Mostrar só alguns estilos como opção no chat já é uma forma de curadoria/exclusão — quem decide quais estilos entram na lista?** *(responder já)*

  **Resposta:** o EDA pode informar essa decisão, mas não pode tomá-la — "quem decide" é uma questão de governança do grupo/produto, não algo que os dados resolvem. O que o EDA mostra é que **qualquer lista curada já herda desigualdades presentes nos dados**: gêneros diferem muito em volume popular (Passo 4, Dados-3), em homogeneidade interna (Passo 5.3 — `sleep`, `german`, `iranian` são mais heterogêneos que a média, logo mais difíceis de representar bem com poucas faixas "típicas") e em quão bem se separam de outros estilos (Passo 5.4). Uma lista de estilos que prioriza os gêneros mais populares/coerentes tende a excluir sistematicamente os mais nichados/heterogêneos — não por má intenção, mas porque são estatisticamente mais difíceis de curar bem. Isso não substitui uma decisão explícita do grupo sobre critério e responsabilidade, mas dá um critério objetivo (volume, coerência interna, separabilidade) para tornar essa decisão menos arbitrária.

## Descartadas

- **Como fatores externos influenciam a popularidade de músicas específicas?** *(cortar sem dó)*
