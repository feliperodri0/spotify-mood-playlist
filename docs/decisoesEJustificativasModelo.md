# Decisões e Justificativas do Modelo — Fase 2 (Vocabulário de Mood e Clustering)

Este documento registra cada decisão metodológica tomada em `entregas/modelo_mood_clustering.ipynb` e a justificativa por trás dela, no mesmo formato de `decisoesEJustificativasEDA.md`. Inclui as correções de rumo feitas durante a própria implementação — registradas explicitamente, não escondidas.

## Reuso do EDA

**Decisão:** carregar `df_clean.parquet` (artefato salvo ao final do EDA) em vez de repetir a limpeza de dados neste notebook.
**Justificativa:** a lógica de limpeza já está implementada, executada e justificada em `eda_spotify.ipynb`/`decisoesEJustificativasEDA.md` — duplicá-la aqui criaria duas fontes de verdade para a mesma decisão, com risco de divergirem silenciosamente se uma for alterada e a outra não.

## Calibração externa (MTG-Jamendo)

**Decisão:** validar quais audio features realmente diferenciam mood usando uma fonte de dados externa e independente do catálogo Spotify, antes de decidir qualquer coisa sobre o vocabulário.
**Justificativa:** calibrar e testar uma escolha usando os mesmos dados infla artificialmente a confiança no resultado (não haveria como o teste discordar da calibração). O MTG-Jamendo foi escolhido por ter tags de mood atribuídas por humanos e descritores acústicos abertos (licença Creative Commons).

**Decisão:** baixar apenas os descritores AcousticBrainz/Essentia pré-computados (25 de 100 shards, ~121 MB), não o áudio completo (152 GB).
**Justificativa:** os descritores já contêm `bpm`, `danceability`, `avg_loudness`, `dissonance` e `dynamic_complexity` por faixa — suficiente para testar se esses descritores diferenciam as tags de mood, sem o custo de processar áudio bruto. 25 shards (4.866 faixas) já cobrem bem os principais tags de mood candidatos, sem necessidade de baixar os 100 shards completos para esse propósito.

## Seleção de features (correção de rumo)

**Decisão original (revertida):** usar as 7 features com maior η² de ANOVA calculado no Passo 5.4 do EDA — critério que mede poder discriminativo para `track_genre`, não para mood.
**Por que foi revertida:** gênero e mood são conceitos correlacionados, mas não idênticos. Reutilizar um critério de seleção validado para um alvo diferente do alvo real da tarefa é uma lacuna metodológica — a seleção "parecia" razoável, mas não tinha validação própria para o problema que o notebook resolve.

**Decisão final:** selecionar features via (1) filtro de redundância por correlação e (2) método wrapper comparando qualidade de clustering (silhouette, via K-Means) entre subconjuntos candidatos, restrito aos subconjuntos que preservam a capacidade de diferenciar as 8 palavras do vocabulário de mood.
**Justificativa:** são as duas técnicas apropriadas para uma tarefa não-supervisionada (clustering) sem variável-alvo direta disponível. O filtro de redundância (unsupervised) identificou `energy`×`loudness` (r=0,76) e `energy`×`acousticness` (r=-0,73) como pares altamente correlacionados — candidatos a remoção de uma das duas. O método wrapper testou 6 subconjuntos e mediu silhouette real de cada um.

**Decisão:** usar K-Means (não GMM) como algoritmo de avaliação no método wrapper, mesmo o algoritmo final sendo GMM.
**Justificativa:** silhouette é uma métrica baseada em distância euclidiana — comparar GMM por essa métrica seria injusto, pois GMM otimiza verossimilhança e pode formar componentes alongados/sobrepostos por design, não círculos compactos. K-Means, que otimiza diretamente a soma de distâncias que o silhouette mede, é o proxy de avaliação padrão para esse tipo de comparação, mesmo quando o modelo de produção usa outro algoritmo.

**Decisão:** não escolher automaticamente o subconjunto de maior silhouette (`E_minimalista`, 4 features, 0,2438); escolher `C_sem_loudness` (6 features, 0,2216) — o melhor **entre os que preservam todas as dimensões necessárias ao vocabulário**.
**Justificativa:** `E_minimalista` remove `instrumentalness` e `speechiness`, inviabilizando a palavra `Instrumental`; `D_sem_valence` (0,2352) remove `valence`, inviabilizando `Feliz`/`Melancolico`. O método wrapper otimiza separação geométrica pura, sem noção do vocabulário de produto que a clusterização precisa representar — seguir cegamente o maior número teria otimizado o critério errado. `C_sem_loudness` ainda é uma melhoria real sobre a escolha original (0,2216 vs. 0,1993 do conjunto de 7 features), não apenas uma correção de escopo.

## Vocabulário de mood

**Decisão:** ancorar cada palavra em quantis reais da distribuição do catálogo (`df_clean`), não em valores estimados a olho.
**Justificativa:** usar quantis próprios do dataset garante que "alto"/"baixo" correspondam ao que de fato é alto/baixo *neste* catálogo. Features com mediana em zero (`acousticness`, `instrumentalness`, `speechiness` — Passo 3 do EDA) usam quantil mais extremo (p90) para "alto", já que p75 ainda captura valores próximos de zero para essas colunas.

**Decisão:** corrigir a âncora de `Melancolico` de `energy` no p25 para p10, após validação qualitativa mostrar que a âncora original capturava metal/industrial em vez de música triste e calma.
**Justificativa:** `valence` baixa sozinha não distingue "triste e calmo" de "raivoso e intenso" — ambos têm tom emocional negativo, mas energia muito diferente. A âncora original não forçava `energy` baixo o suficiente. Corrigido, o resultado mais próximo da âncora passou a ser "Something In The Way" (Nirvana) — validação qualitativa concreta, não apenas ajuste numérico sem checagem.

## Clustering (GMM)

**Decisão:** usar Gaussian Mixture Model como algoritmo final, não K-Means.
**Justificativa:** o Passo 5.4 do EDA já mostrou fronteiras fracas entre estilos (silhouette baixo, ARI≈0 contra `track_genre` em clustering por faixa individual). GMM expõe probabilidade de pertencimento por faixa em vez de atribuição rígida — mais compatível com dados sem separação natural nítida.

**Decisão:** fixar `K=8` por necessidade de produto (tamanho do vocabulário), não pelo BIC.
**Justificativa:** o BIC foi testado de K=6 a K=14 (e, numa exploração anterior com 7 features, até K=30) e não converge — segue caindo sem formar um "cotovelo" identificável. Isso é consistente com a ausência de estrutura de cluster natural forte já documentada no EDA. Sem um K estatisticamente ótimo, a escolha é orientada pelo requisito de produto (8 palavras de mood no vocabulário), com a ausência de otimalidade estatística registrada explicitamente, não escondida.

## Rotulagem de mood (correção de rumo)

**Decisão original (revertida):** rotular cada cluster do GMM pela palavra de mood mais próxima do seu centroide.
**Por que foi revertida:** o GMM agrupa faixas pela densidade natural dos dados, sem nenhum compromisso com as 8 palavras do vocabulário. Na prática, apenas 4 das 8 palavras foram usadas como rótulo de algum dos 8 clusters — não há garantia de que os centroides encontrados pelo algoritmo caiam perto de todas as regiões que o vocabulário define.

**Decisão final:** classificar cada faixa individualmente pela âncora de mood mais próxima (nearest-anchor), independente do cluster do GMM.
**Justificativa:** garante cobertura completa das 8 palavras por construção (é uma atribuição direta por distância, não dependente de onde o clustering colocou 8 centroides). O GMM continua sendo informação complementar útil (estrutura de densidade do catálogo, reaproveitável na Fase 3 para o sequenciamento), mas deixou de ser o mecanismo de atribuição de mood.

## Validação qualitativa

**Decisão:** inspecionar manualmente as faixas mais próximas de cada âncora antes de aceitar o vocabulário como pronto, mesmo com seleção de features e âncoras baseadas em quantis reais.
**Justificativa:** validação estatística (silhouette, calibração externa) não substitui checagem de sentido musical — foi exatamente essa checagem que revelou o problema da âncora de `Melancolico`, que nenhuma métrica agregada teria detectado sozinha.

## Seleção de candidatas (Seção 5 do plano)

**Decisão:** calcular o ponto-alvo de uma consulta multi-palavra como a média simples das âncoras (no espaço transformado) das palavras escolhidas.
**Justificativa:** é a forma mais direta de combinar 2+ regiões do espaço de mood num único ponto de busca — pedir "Calmo" + "Instrumental" deve retornar faixas num meio-termo entre as duas, não faixas extremamente próximas de uma só. Validado com o próprio exemplo do plano: a combinação retornou 5 faixas rotuladas `Calmo` e 5 rotuladas `Instrumental` entre as 10 mais próximas — nem dominado por uma palavra, nem irrelevante para nenhuma das duas.

**Decisão:** usar `NearestNeighbors` com distância euclidiana, a mesma métrica já usada na atribuição de mood por faixa (Passo anterior), em vez de cosseno (a outra opção mencionada no plano).
**Justificativa:** manter a mesma métrica de distância em todo o notebook evita que "faixa mais próxima da âncora X" signifique coisas diferentes dependendo de qual parte do notebook está sendo consultada. Não havia motivo identificado para preferir cosseno (mais comum quando a magnitude do vetor não deveria importar, ex: contagem de palavras — não é o caso aqui, onde os valores já foram padronizados).

**Decisão:** validar a implementação com um teste de consistência (pedir 1 palavra isolada deve concordar com o mood já atribuído àquela faixa).
**Justificativa:** são dois mecanismos computacionalmente distintos calculando coisas conceitualmente equivalentes no caso de 1 palavra (nearest-anchor direto vs. `NearestNeighbors` com N vizinhos) — se discordassem, indicaria um bug de implementação. Concordância de 100% (20 de 20 faixas) confirma que os dois mecanismos são consistentes entre si.

**Decisão:** incluir o `NearestNeighbors` treinado no artefato salvo (`modelo_mood.joblib`), junto com os transformadores e o GMM.
**Justificativa:** evita ter que refazer o fit (que depende de ter `X`, a matriz transformada de 113.549×6, em memória) toda vez que a Fase 3/4 precisar consultar candidatas — o artefato salvo já contém tudo que é necessário para reconstruir a função `selecionar_candidatas` sem reprocessar o catálogo.

## Limitações registradas (não resolvidas, apenas documentadas)

- Nenhum descritor de baixo nível testado (Spotify ou Essentia/AcousticBrainz) mede valência diretamente — o eixo positivo/negativo do vocabulário depende inteiramente da coluna `valence` do Spotify (modelo proprietário, não auditável), sem validação externa equivalente à obtida para o eixo de energia/arousal.
- O método wrapper foi avaliado com K-Means como proxy; não há garantia de que o subconjunto de features vencedor nesse proxy seja exatamente o ótimo para o GMM final (algoritmos diferentes podem, em princípio, preferir conjuntos de features ligeiramente diferentes) — aceitável dado que o proxy é a prática padrão para esse tipo de comparação, mas não é uma prova formal de otimalidade para o GMM especificamente.
- A distribuição de faixas por palavra de mood é desigual (8.799 a 18.925) — não foi feito nenhum balanceamento; se isso for um problema para a fase de interface (ex: `Acustico` ter poucas opções), precisa ser tratado explicitamente na Fase 4, não fica resolvido aqui.
