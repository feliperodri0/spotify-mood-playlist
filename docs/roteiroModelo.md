# Roteiro do Modelo — Fase 2: Vocabulário de Mood e Clustering

Documento de acompanhamento do notebook `entregas/modelo_mood_clustering.ipynb`, implementando a Fase 2 do plano descrito em `planejamentoModelo.md`. Registra os passos executados, na ordem em que o notebook avança. As justificativas detalhadas de cada decisão estão em `decisoesEJustificativasModelo.md`; este documento é o roteiro/índice, não o raciocínio completo.

## Passo 0 — Carregamento do catálogo

Carregamento de `df_clean.parquet`, artefato salvo ao final do EDA (`eda_spotify.ipynb`) — 113.549 faixas já limpas e validadas, sem repetir a lógica de limpeza documentada em `decisoesEJustificativasEDA.md`.

## Passo 1 — Calibração externa (MTG-Jamendo)

**Objetivo:** validar quais audio features realmente diferenciam mood, usando uma fonte de dados independente do catálogo Spotify, antes de decidir qualquer coisa sobre features ou vocabulário.

**Como os dados foram obtidos:**
1. Metadados de tags (`autotagging_moodtheme.tsv`, 18.486 faixas com tags de mood humanas) baixados direto do repositório oficial no GitHub (`MTG/mtg-jamendo-dataset`).
2. Em vez do áudio completo (152 GB), foram identificados — via leitura do script oficial `scripts/download/download.py` — os descritores acústicos pré-computados (formato AcousticBrainz/Essentia), distribuídos em 100 arquivos `.tar.gz` (~4,7 MB cada) hospedados na CDN da Freesound.
3. Baixados 25 dos 100 shards (~121 MB, 4.866 faixas) — amostra suficiente para calibração sem precisar do conjunto completo.
4. Extração dos JSONs e cruzamento com o TSV de tags por `track_id`/caminho do arquivo, gerando uma tabela faixa-a-faixa com `bpm`, `danceability` (Essentia), `avg_loudness`, `dissonance` e `dynamic_complexity`.
5. Agregação por tag de mood (média de cada descritor por tag), salva em [`calibracao_jamendo.csv`](../entregas/calibracao_jamendo.csv).

**Persistência:** os dados brutos foram baixados novamente e salvos dentro do projeto, em `dados_externos/mtg_jamendo/`:
- `moodtheme_tags.tsv` — metadados de tags originais (18.486 faixas, ~1,8 MB).
- `raw_shards/` — os 25 arquivos `.tar.gz` originais dos descritores AcousticBrainz/Essentia (~109 MB).
- `calibracao_faixas.parquet` — tabela faixa-a-faixa já cruzada com as tags (4.866 linhas, ~320 KB) — o resultado útil, pronto pra reanálise sem precisar reextrair os shards.

Os JSONs individuais extraídos dos shards não foram mantidos (redundantes com `calibracao_faixas.parquet`); para recalcular outros descritores não capturados na tabela, os `.tar.gz` em `raw_shards/` podem ser reextraídos a qualquer momento. A tabela agregada por tag (`entregas/calibracao_jamendo.csv`) foi conferida contra essa reconstrução — os valores batem exatamente.

**Resultado:** `avg_loudness` e `danceability` diferenciam mood de forma clara e ordenada entre as tags testadas; `bpm` e `dissonance` quase não variam. Esse padrão bate com o encontrado de forma independente no Passo 5.4 do EDA (via η² de ANOVA no catálogo Spotify) — validação cruzada entre duas fontes de dados distintas. Nenhum descritor testado mede valência diretamente (limitação registrada).

## Passo 2 — Seleção de features (correção de rumo)

**Tentativa inicial (revertida):** reaproveitar as 7 features de maior η² de ANOVA do Passo 5.4 do EDA — um critério validado para `track_genre`, não para mood.

**Seleção final, validada para a tarefa real:**
1. **Filtro de redundância** (correlação): identificados `energy`×`loudness` (r=0,76) e `energy`×`acousticness` (r=-0,73) como pares redundantes.
2. **Método wrapper**: 6 subconjuntos de features candidatos testados via K-Means + silhouette (K-Means usado como proxy de avaliação, não como algoritmo final) — resultado ordenado do melhor para o pior: `E_minimalista` (0,2438) > `D_sem_valence` (0,2352) > `C_sem_loudness` (0,2216) > `F_sem_energy` (0,2109) > `B_7_original` (0,1993) > `A_todas_9` (0,1455).
3. **Restrição de escopo:** os dois subconjuntos de maior silhouette quebravam a capacidade de representar o vocabulário completo (removiam features que `Instrumental`, `Feliz` ou `Melancolico` precisam) — descartados apesar da pontuação melhor.

**Decisão final:** 6 features — `energy`, `valence`, `danceability`, `acousticness`, `instrumentalness`, `speechiness` (conjunto `C_sem_loudness`) — melhor silhouette entre os que preservam o vocabulário completo, e melhoria real sobre a escolha original (0,2216 vs. 0,1993).

## Passo 3 — Vocabulário de mood

8 palavras (`Energetico`, `Feliz`, `Dancante`, `Calmo`, `Melancolico`, `Intenso`, `Instrumental`, `Acustico`), cada uma ancorada em quantis reais da distribuição do catálogo (p10/p25/p50/p75/p90 conforme a assimetria de cada feature), não em valores estimados a olho.

## Passo 4 — Pré-processamento

`PowerTransformer` (Yeo-Johnson) nas 3 colunas com pico perto de zero (`acousticness`, `instrumentalness`, `speechiness`), seguido de `StandardScaler` em todas as 6 features — aplicado tanto ao catálogo quanto às âncoras do vocabulário, no mesmo espaço transformado.

## Passo 5 — Clustering (GMM)

- BIC testado de K=6 a K=14 (e, numa exploração anterior com 7 features, até K=30) — não converge, segue caindo sem "cotovelo" identificável.
- `K=8` fixado por necessidade de produto (tamanho do vocabulário), não por otimização estatística — decisão registrada explicitamente, não escondida atrás de uma aparência de rigor que não existe.
- GMM final treinado: probabilidade média da atribuição mais provável = 0,942.

## Passo 6 — Rotulagem de mood (correção de rumo)

**Tentativa inicial (revertida):** rotular cada um dos 8 clusters do GMM pela palavra de mood mais próxima do seu centroide — cobriu apenas 4 das 8 palavras, porque os centroides do GMM não têm compromisso de coincidir com as regiões do vocabulário.

**Correção final:** cada faixa individual classificada pela âncora de mood mais próxima diretamente (nearest-anchor), independente do cluster do GMM — garante cobertura completa das 8 palavras por construção. Distribuição final: de 8.799 (`Acustico`) a 18.925 (`Energetico`) faixas por palavra.

## Passo 7 — Validação qualitativa (correção de rumo)

Inspeção manual das faixas mais próximas de cada âncora. Encontrado e corrigido um erro real: a âncora original de `Melancolico` (energia no p25, moderada) capturava metal/industrial em vez de música triste e calma. Corrigida para energia no p10 — o resultado mais próximo passou a ser *"Something In The Way"* (Nirvana), uma validação concreta e reconhecível.

## Passo 8 — Seleção de candidatas dado o mood escolhido (Seção 5 do plano)

**Objetivo:** implementar o mecanismo que faltava entre "cada faixa tem 1 mood mais próximo atribuído" (Passo 6) e o sequenciamento (Fase 3, ainda não implementada) — dado que o usuário escolheu uma ou mais palavras, encontrar as faixas mais adequadas à combinação.

**Como foi feito:**
1. Alvo = média das âncoras (no espaço transformado) das palavras escolhidas — 1 palavra dá o alvo exato daquela âncora; 2+ palavras dão o ponto médio entre elas.
2. `sklearn.neighbors.NearestNeighbors` (distância euclidiana, mesma métrica já usada na atribuição de mood por faixa) retorna as N faixas mais próximas do alvo, no catálogo inteiro (113.549 faixas × 6 features).
3. Função `selecionar_candidatas(palavras, n)` encapsula o mecanismo.

**Nota:** o texto original do plano descrevia isso no "espaço das 7 features" — desatualizado após a correção da Seção 2 (Passo 2 deste roteiro), que reduziu para 6. A implementação usa as 6 features validadas, não as 7 originais.

**Validação:** consulta de exemplo do próprio plano (`"Calmo"` + `"Instrumental"`) retornou uma mistura plausível das duas palavras (5 faixas rotuladas `Calmo`, 5 rotuladas `Instrumental` entre as 10 mais próximas do alvo combinado). Checagem de consistência: pedindo só 1 palavra (`"Energetico"`), **100% das 20 candidatas retornadas já tinham esse mesmo mood atribuído** na etapa anterior — os dois mecanismos concordam.

## Passo 9 — Artefatos salvos

- `entregas/modelo_mood.joblib` — `PowerTransformer`, `StandardScaler`, GMM treinado, `NearestNeighbors` treinado (Passo 8), features selecionadas e âncoras do vocabulário.
- `entregas/catalogo_com_mood.parquet` — catálogo completo com `cluster`, `cluster_prob`, `mood` e `mood_distancia` por faixa.

Ambos prontos para reuso na Fase 3 (sequenciamento por transição suave), sem necessidade de retreinar nada.
