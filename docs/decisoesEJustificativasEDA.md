# Decisões e Justificativas da Análise Exploratória — Spotify Tracks Dataset

Este documento registra cada decisão metodológica tomada durante o EDA (`entregas/eda_spotify.ipynb`) e a justificativa por trás dela. O objetivo é permitir auditar o raciocínio da análise sem precisar reconstruí-lo a partir do código — útil tanto para revisão do grupo quanto para justificar escolhas na apresentação final.

## Princípio orientador

**Decisão:** nenhuma abordagem de modelagem (clustering, classificação, recomendação etc.) é definida durante o EDA.
**Justificativa:** o objetivo desta fase é compreender os dados; decidir o rumo de modelagem antes disso inverteria a lógica do Investigate/CBL e correria o risco de moldar a análise para confirmar uma escolha já feita, em vez de deixar os dados informarem a escolha.

## Passo 1 — Configuração e primeira inspeção

**Decisão:** usar `index_col=0` no `read_csv`.
**Justificativa:** o CSV original tem uma coluna sem nome no início (índice de linha herdado da exportação); sem essa opção, ela seria carregada como uma coluna de dado inútil.

**Decisão:** documentar um dicionário de dados a partir da fonte oficial (Hugging Face/Kaggle), antes de interpretar qualquer coluna.
**Justificativa:** interpretar colunas "no chute" (ex: assumir o que `key` ou `time_signature` significam) é arriscado — a documentação da fonte revelou, por exemplo, que `key = -1` tem significado especial ("não detectado") e que `time_signature` deveria variar de 3 a 7, informações que não seriam óbvias só olhando os números.

## Passo 2 — Qualidade dos dados

**Decisão:** remover a linha com `artists`/`album_name`/`track_name` ausentes (1 linha).
**Justificativa:** são colunas de texto identificador — não há base numérica ou categórica para estimar/imputar um nome de artista. A mesma linha também apresentava `duration_ms = 0` e `popularity = 0`, indicando um registro corrompido como um todo, não três problemas independentes. Afeta apenas 1 linha em 114.000 (< 0,001%), custo de remoção desprezível.

**Decisão:** remover as 450 linhas 100% duplicadas (idênticas em todas as colunas, incluindo `track_genre`).
**Justificativa:** duplicata exata não agrega informação nova — é, por definição, erro de coleta/carga. Mantê-las infla artificialmente a contagem de qualquer gênero afetado sem motivo legítimo.

**Decisão:** manter as 23.809 linhas com `track_id` repetido em gêneros diferentes (não tratar como duplicata).
**Justificativa:** verificação rigorosa (comparando, para cada `track_id`, número de linhas vs. número de gêneros distintos) confirmou zero casos de repetição não explicada por gênero diferente — cada linha "repetida" corresponde a uma classificação de gênero legítima e distinta. Remover destruiria informação real do catálogo (uma música pertencer a múltiplos gêneros).

**Decisão:** manter `tempo == 0` e `time_signature == 0` (163 linhas), sem imputar ou remover.
**Justificativa:** essas linhas se concentram fortemente no gênero `sleep` (138 de 163) e em gêneros sem pulsação rítmica marcada (`ambient`, `guitar`, `world-music`). O valor zero reflete o algoritmo de análise de áudio do Spotify não detectando ritmo em faixas genuinamente arrítmicas — é informação real ("sem tempo detectável"), não erro de coleta.

**Decisão:** manter `time_signature == 1` (973 linhas), apesar de estar fora da faixa documentada (3–7).
**Justificativa:** diferente do caso `== 0`, essas linhas têm `tempo` sempre preenchido e plausível (64–217 BPM), e os gêneros envolvidos (`grindcore`, `classical`, `comedy`, entre outros) são plausivelmente associados a métrica atípica ou irregular. Não há evidência de corrupção de dado. **Ressalva:** essa é uma interpretação fundamentada em evidência indireta, não uma certeza documentada pela fonte — registrada como limitação no notebook.

**Decisão:** não tomar nenhuma ação sobre `key`.
**Justificativa:** checagem direta confirmou 0 ocorrências de `key == -1` (o valor oficial para "não detectado") — a coluna está inteiramente preenchida com tonalidades reais, sem necessidade de tratamento.

**Resultado da limpeza:** `df.drop_duplicates().dropna()` → 114.000 → 113.549 linhas (`df_clean`), usado a partir do Passo 3.

## Passo 3 — Distribuição das variáveis numéricas

**Decisão:** usar histogramas com `bins=50` para as 11 colunas numéricas contínuas.
**Justificativa:** 50 faixas oferece granularidade suficiente para revelar a forma da distribuição (picos, caudas) sem poluir o gráfico com ruído de bins excessivamente estreitos.

**Decisão:** excluir `key`, `mode`, `time_signature` e `explicit` do grid de histogramas.
**Justificativa:** são variáveis categóricas/discretas com poucos valores possíveis — histograma (que pressupõe uma escala contínua dividida em faixas) não é a ferramenta apropriada; essas colunas foram tratadas com gráfico de barras no Passo 4.

**Decisão:** refazer o histograma de `duration_ms` limitando o eixo ao percentil 99, sem remover nenhum dado do dataset.
**Justificativa:** o outlier de ~87 minutos (identificado no Passo 1) esticava a escala do eixo X a ponto de esconder a forma real da distribuição. Usar um corte por percentil (em vez de um valor fixo arbitrário, como "10 minutos") ajusta a visualização de forma proporcional aos próprios dados, sem descartar nenhum registro da análise.

**Decisão:** adotar a regra de Bulmer (1979) — \|skew\| < 0,5 simétrica, 0,5–1 moderada, ≥ 1 forte — como critério de classificação da assimetria.
**Justificativa:** fornece um limiar de referência da literatura estatística, em vez de julgamento subjetivo sobre "o que conta como assimétrico". Optou-se por esse critério de magnitude em vez de um teste de significância formal porque, com `n = 113.549`, o erro-padrão do skew é muito pequeno (~0,007), tornando praticamente qualquer desvio de zero "estatisticamente significativo" — o que tornaria o teste pouco informativo na prática.

## Passo 4 — Variáveis categóricas e discretas

**Decisão:** não plotar as 114 categorias de `track_genre` em um gráfico de barras.
**Justificativa:** com contagens quase uniformes (904–1.000 por gênero após a limpeza), um gráfico com 114 barras finas seria pouco legível e acrescentaria pouco à tabela numérica já produzida, que evidencia o desbalanceamento residual de forma mais clara.

**Decisão:** usar gráfico de barras (`countplot`), não histograma, para `key`, `mode`, `time_signature` e `explicit`.
**Justificativa:** são variáveis categóricas/discretas — a noção de "faixa contínua" (bin) do histograma não se aplica; cada categoria deve ser representada por exatamente uma barra.

## Passo 5 — Relações entre variáveis

**Decisão:** calcular a matriz de correlação de Pearson apenas sobre as colunas numéricas contínuas (`popularity` + audio features), excluindo `key`, `mode`, `time_signature` e `explicit`.
**Justificativa:** o coeficiente de Pearson pressupõe variáveis intervalares/contínuas. `key` é uma escala nominal-cíclica (o valor 11 não é "maior" que 0 em nenhum sentido musical), `mode` é binária, e `time_signature`/`explicit` são discretas/categóricas — aplicar Pearson diretamente a elas produziria números sem interpretação musical válida.

**Decisão:** selecionar 8 gêneros contrastantes (`sleep`, `classical`, `acoustic`, `jazz`, `pop`, `hip-hop`, `edm`, `death-metal`) para os boxplots comparativos, em vez dos 114 gêneros completos.
**Justificativa:** 114 categorias em um boxplot tornariam o gráfico ilegível. A seleção cobre deliberadamente o espectro de energia/atmosfera sonora observado no dataset (do mais calmo ao mais intenso), permitindo checar visualmente, em nível de gênero, se as relações encontradas na matriz de correlação (Passo 5.1) se sustentam — não é uma amostra aleatória, é uma escolha proposital para maximizar contraste e poder de checagem visual.

**Decisão:** comparar especificamente `energy`, `acousticness`, `danceability` e `valence` nos boxplots por gênero.
**Justificativa:** são os pares que se destacaram na matriz de correlação (5.1) — `energy`×`acousticness` (correlação forte, -0,73) e `danceability`×`valence` (correlação moderada, 0,48) — escolhidos para confirmar, com uma visualização diferente, se os padrões numéricos da correlação se refletem em diferenças reais e visíveis entre gêneros.

## Limitações registradas (não resolvidas, apenas documentadas)

- `time_signature == 1`: interpretação plausível (compasso atípico), não uma certeza confirmada pela documentação da fonte.
- `explicit`: o valor `False` mistura "confirmadamente sem conteúdo explícito" e "desconhecido" — qualquer proporção calculada a partir dessa coluna é um piso, não o valor real.
- `track_genre`: a fonte documenta 125 gêneros, mas o arquivo real contém apenas 114 — divergência entre documentação pública e dados entregues, sem explicação encontrada.
- `popularity`: sem correlação linear detectável com nenhuma audio feature — em aberto para a fase de hipóteses, não uma conclusão definitiva (o Pearson só captura relações lineares).
- **O η² de ANOVA do Passo 5.4 (poder discriminativo de cada feature) foi calculado usando `track_genre` como variável-alvo — não deve ser reaproveitado como critério de seleção de features para outra tarefa (ex: clustering de mood) sem revalidação.** Isso de fato aconteceu na primeira versão do notebook de modelagem (`entregas/modelo_mood_clustering.ipynb`): a seleção de features para o vocabulário de mood reutilizou o η² por gênero sem checagem própria. Foi corrigido com uma seleção de features validada especificamente para a tarefa de mood — ver `decisoesEJustificativasModelo.md`.
- **A checagem de duplicatas do Passo 2.2 cobriu duas formas de repetição (linha 100% idêntica; `track_id` repetido em gêneros diferentes), mas não uma terceira: a mesma música (mesmo `track_name` + `artists`) sob um `track_id` completamente diferente.** Descoberto durante a implementação da Fase 3 (`entregas/sequenciamento_playlist.ipynb`), ao gerar uma playlist de teste com a mesma música repetida 9 vezes. Medido no catálogo inteiro: **9,4% dos 89.740 `track_id` únicos são "repetição" de um `(track_name, artists)` já visto** — casos extremos como faixas natalinas reeditadas anualmente em compilações chegam a 30-45 `track_id` diferentes para a mesma canção (ex: "Rockin' Around The Christmas Tree", Brenda Lee: 45 `track_id`). Esse tipo de duplicata não afeta as conclusões estatísticas do EDA (cada `track_id` ainda é uma medição de audio features legítima), mas é uma limitação real para qualquer uso que apresente faixas individuais a um usuário final (ex: geração de playlist) — tratado na Fase 3 via deduplicação por `(track_name, artists)`, não só `track_id`. Ver `decisoesEJustificativasSequenciamento.md`.
