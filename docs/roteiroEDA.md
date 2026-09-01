# Roteiro da Análise Exploratória de Dados — Spotify Tracks Dataset

Documento de acompanhamento do notebook `entregas/eda_spotify.ipynb`, fase **Investigate** do CBL. Registra os passos já executados e os planejados, na ordem em que a análise avança. Nenhuma abordagem de modelagem é definida durante o EDA — essa decisão é tomada somente após a conclusão desta etapa, com base nos achados aqui documentados.

## Concluído

### Passo 1 — Configuração e primeira inspeção
- Carregamento do dataset (`dataset.csv`, 114.000 linhas × 20 colunas).
- Dicionário de dados completo, com definição de cada coluna a partir da documentação oficial da fonte (Hugging Face / Kaggle, *Spotify Tracks Dataset*).
- Tipos de dado (`df.info()`) e resumo estatístico (`df.describe()`), com legenda explicando cada estatística exibida.
- Primeiras hipóteses de problema: 1 linha com valores ausentes; mínimos suspeitos (`= 0`) em `duration_ms`, `tempo` e `time_signature`.

### Passo 2 — Qualidade dos dados
- **2.1 Valores ausentes:** confirmado 1 registro com `artists`/`album_name`/`track_name` ausentes, coincidindo com `duration_ms = 0` e `popularity = 0` — um único registro corrompido, não três problemas separados.
- **2.2 Duplicatas:** 450 linhas 100% idênticas (erro de coleta/carga) e 23.809 linhas com `track_id` repetido explicadas por classificação legítima em múltiplos gêneros (verificado linha a linha, sem sobra não explicada).
- **2.3 Zeros suspeitos:** `tempo == 0` e `time_signature == 0` (163 linhas) não são erro — refletem o algoritmo de análise de áudio do Spotify sem detectar ritmo em faixas de fato arrítmicas (majoritariamente gênero `sleep`).
- **2.4 Conferência com a documentação oficial:** `key == -1` não ocorre no dataset (sem ação necessária); identificado um caso adicional não previsto — `time_signature == 1` (973 linhas, fora da faixa documentada de 3–7) — com tempo válido presente, indicando compasso atípico e não falha de detecção.
- **Limpeza aplicada:** remoção de 1 linha corrompida + 450 duplicatas exatas → `df_clean` com 113.549 linhas. Repetição por múltiplos gêneros e os zeros de `tempo`/`time_signature` foram mantidos por serem informação legítima.
- Documento de apoio: [`analiseSobreAusenciadeDados.md`](./analiseSobreAusenciadeDados.md) — técnicas de tratamento de dados ausentes em colunas numéricas (deleção vs. imputação), para casos futuros mais complexos que o encontrado aqui.

### Passo 3 — Distribuição individual das variáveis numéricas
- Histogramas das 11 colunas numéricas contínuas (`popularity`, `duration_ms`, `danceability`, `energy`, `loudness`, `speechiness`, `acousticness`, `instrumentalness`, `liveness`, `valence`, `tempo`) + assimetria (skewness) de cada uma.
- Correção de visualização em `duration_ms` (outlier de ~87 min distorcia a escala do gráfico; refeito com o eixo limitado ao percentil 99).
- Padrões identificados: variáveis aproximadamente simétricas (`danceability`, `tempo`, `valence`, `popularity`); concentradas no lado alto (`energy`, `loudness`); e variáveis "detectoras de característica", com pico perto de zero e cauda longa (`speechiness`, `instrumentalness`, `liveness`, `acousticness`).
- Achado a aprofundar: pico isolado de `popularity = 0` (quase 18.000 faixas), possivelmente um subgrupo distinto do restante do catálogo.
- Critério de interpretação da assimetria documentado (regra de Bulmer, 1979) e as 11 variáveis reclassificadas por magnitude — ver [`decisoesEJustificativasEDA.md`](./decisoesEJustificativasEDA.md).

### Passo 4 — Variáveis categóricas e discretas
- Balanceamento real de `track_genre`: **114 gêneros** (não 125, como diz a documentação da fonte), quase uniformes após a limpeza (904–1.000 por gênero); `romance` (-96) e `classical` (-67) foram os mais afetados pela remoção de duplicatas exatas.
- Distribuição de `key`, `mode`, `time_signature` e `explicit` em gráficos de barra: predominância de tonalidade maior, compasso 4/4, e conteúdo não-explícito (com ressalva de que `explicit=False` mistura "confirmado" e "desconhecido").

### Passo 5 — Relações entre variáveis
- Matriz de correlação de Pearson entre as audio features e `popularity`: **`popularity` não tem correlação linear relevante com nenhuma audio feature** (todas abaixo de 0,1 em módulo). Par mais correlacionado: `energy`×`loudness` (0,76); mais anti-correlacionado: `energy`×`acousticness` (-0,73).
- Boxplots de `energy`, `acousticness`, `danceability` e `valence` para 8 gêneros contrastantes (`sleep`, `classical`, `acoustic`, `jazz`, `pop`, `hip-hop`, `edm`, `death-metal`): confirmam visualmente o eixo `energy`/`acousticness` em nível de gênero, e mostram que `danceability` varia de forma relativamente independente de `energy` (ex: `death-metal` e `classical` têm dançabilidade parecida apesar de energia oposta).
- **5.3 Estrutura de estilos:** clustering hierárquico dos 114 gêneros (média das 9 audio features) encontra famílias musicalmente coerentes (gêneros brasileiros, metal/punk, eletrônica de pista, um cluster "calmo/instrumental" próximo do conceito de lofi), mas também um cluster grande e heterogêneo (33 gêneros) sem separação clara. Homogeneidade interna moderada (mediana da razão std-gênero/std-global = 0,73). Co-ocorrência de gênero em faixas multi-rotuladas é musicalmente coerente (`reggae`+`reggaeton`, `punk`+`punk-rock`, `edm`+`house`), não arbitrária. Confirmado: **"lofi" não existe como rótulo de gênero** no dataset; entre os gêneros mais próximos desse conceito, `chill` é um dos mais populares do catálogo (5º de 114) enquanto `study`/`sleep` são mais nichados (72º/61º) — sem viés uniforme contra "estilos calmos".
- **5.4 Clustering ao nível de faixa vs. gênero:** K-Means (K=8) sobre faixas individuais **não recupera** `track_genre` (Adjusted Rand Index = 0,017; NMI = 0,17) — a estrutura de família encontrada em 5.3 existe na média por gênero, mas se dilui bastante ao nível de faixa individual. Poder discriminativo por feature (η² de ANOVA): `acousticness`, `energy`, `instrumentalness`, `loudness`, `speechiness` e `danceability` concentram a maior parte do sinal (η²=0,41–0,49); `key` é essencialmente inútil para diferenciar gênero (η²=0,005).

Documento de apoio com o raciocínio completo por trás de cada decisão de limpeza, visualização e escopo tomada até aqui: [`decisoesEJustificativasEDA.md`](./decisoesEJustificativasEDA.md).

## Planejado (ainda não executado)

### Passo 6 — Hipóteses e conclusões do Investigate
- Revisão das guiding questions levantadas na fase inicial do CBL, confrontando cada uma com os achados do EDA.
- Consolidação dos achados que devem embasar a escolha da abordagem de modelagem na fase Act — decisão que não é tomada neste documento nem no EDA, apenas instruída por ele.
