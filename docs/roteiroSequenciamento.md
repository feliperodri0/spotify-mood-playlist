# Roteiro da Fase 3 — Sequenciamento por Transição Suave

Documento de acompanhamento do notebook `entregas/sequenciamento_playlist.ipynb`, implementando a Seção 6 do plano descrito em `planejamentoModelo.md`. Justificativas detalhadas em `decisoesEJustificativasSequenciamento.md`.

## Passo 0 — Carregamento

Carrega `df_clean.parquet` (catálogo completo, incluindo `tempo`/`key`/`mode` — não usados no clustering da Fase 2, mas necessários aqui) e `modelo_mood.joblib` (transformadores + `knn` treinados na Fase 2). As duas tabelas de origem (`df_clean.parquet` e `catalogo_com_mood.parquet`) têm a mesma ordem posicional de linhas — combinadas por atribuição direta de coluna, não por `merge` em `track_id` (que multiplicaria linhas, dado que 23.809 delas têm `track_id` repetido em gêneros diferentes).

## Passo 1 — Compatibilidade harmônica (Camelot Wheel)

Mapeamento fixo `key`+`mode` → posição na roda de Camelot (número 1-12 + letra A/menor ou B/maior). Penalidade de transição em 3 níveis: 0,0 (idêntica), 0,15 (relativa ou vizinha), 0,5 (incompatível).

## Passo 2 — Algoritmo de sequenciamento

Nearest-neighbor ambicioso: parte de uma faixa, sempre avança para a candidata não usada de menor custo de transição (distância de audio features + diferença de `tempo` normalizada + penalidade harmônica). Pesos padrão (`tempo=0,5`, `harmônico=1,0`) testados em 6 combinações — resultado consistente e robusto em todas (não sensível à escolha exata dos pesos).

## Passo 3 — Seleção de candidatas com deduplicação (correção de rumo)

**Erro encontrado e corrigido:** a primeira versão de `selecionar_candidatas` deduplicava só por `track_id` — resultado: a música "Happier" (Marshmello;Bastille) apareceu **9 vezes** na playlist gerada, cada ocorrência com `track_id` diferente. Investigado e medido: **9,4% dos `track_id` únicos do catálogo são a mesma música sob um `track_id` diferente** (edições/compilações distintas — casos extremos como faixas natalinas chegam a 30-45 `track_id` para a mesma canção). Esse tipo de duplicata não tinha sido detectado em nenhum passo anterior do EDA.

**Correção:** deduplicação por `(track_name, artists)`, buscando excedente de vizinhos (`n × 6`) para compensar as remoções. Achado retroalimentado em `decisoesEJustificativasEDA.md` como limitação adicional do Passo 2.2.

## Passo 4 — Demonstração e validação

Consulta de exemplo (`Energetico`, 30 candidatas) sequenciada e comparada contra a média de 20 embaralhamentos aleatórios das mesmas candidatas:

| | Δ tempo médio | % transições harmonicamente compatíveis |
|---|---|---|
| Ambicioso | 10,5 BPM | 72% |
| Aleatório (20x) | 20,6 BPM | 18% |

Números finais, já com a deduplicação corrigida — mais altos (menos "bonitos") que o teste inicial com o bug (4,6-6,9 BPM / 79-83%), porque o teste inicial estava inflado por faixas duplicadas com distância ~0 entre si. Reportado o número correto, não o mais favorável.

## Estado atual

Fase 3 implementada e validada. Falta: Fase 4 (Interface) e Fase 5 (Avaliação qualitativa por escuta humana — nenhuma das métricas desta fase substitui isso, ver limitações em `decisoesEJustificativasSequenciamento.md`).
