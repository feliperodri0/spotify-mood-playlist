# Planejamento do Modelo — Playlist por Mood com Transições Suaves

Plano de implementação da abordagem avaliada como viável (com ressalvas) a partir do EDA: agrupar faixas por similaridade acústica, permitir seleção de mood por palavras-chave, e gerar playlists com transições suaves entre faixas. Este documento descreve a arquitetura, as ferramentas e as decisões técnicas — não é código, é o mapa antes da implementação.

## Visão geral do pipeline

```
[Catálogo: df_clean, 113.549 faixas]
        │
        ▼
[Seleção + tratamento de features]  →  7 audio features "mood-relevantes"
        │
        ▼
[Espaço de mood]  →  Clustering (GMM) + vocabulário de palavras ancorado
        │
        ▼
[Usuário escolhe palavras no chat/UI]
        │
        ▼
[Seleção de candidatas]  →  faixas mais próximas do "alvo" pedido
        │
        ▼
[Sequenciamento]  →  ordena por transição suave (distância + tempo + key)
        │
        ▼
[Playlist final]  →  avaliação qualitativa humana
```

## 1. Catálogo

O catálogo de produção é o resultado direto do EDA já concluído: `df_clean` (113.549 faixas, `entregas/eda_spotify.ipynb`), sem necessidade de nova coleta de áudio ou recomputação de features. Carrega em formato leve (`.parquet`, ~15-20 MB) direto na memória do backend, sem exigir banco de dados.

## 2. Features e pré-processamento

- **7 dimensões usadas no clustering**: `energy`, `valence`, `danceability`, `acousticness`, `instrumentalness`, `loudness`, `speechiness` — as que o Passo 5.4 do EDA identificou com poder discriminativo real.
- **Tratamento de assimetria antes de padronizar**: `speechiness`, `instrumentalness` e `acousticness` têm pico forte perto de 0 (Passo 3 do EDA) — aplicar `sklearn.preprocessing.PowerTransformer` (Yeo-Johnson) nessas colunas antes do `StandardScaler`, evitando que a distância euclidiana seja dominada pela cauda longa.
- **`tempo` e `key` ficam fora do clustering**, mas são preservados à parte — não ajudam a definir mood (baixo poder discriminativo, confirmado no Passo 5.4), mas são centrais na etapa de sequenciamento (Seção 6).

## 3. Espaço de mood e vocabulário de palavras

**Base teórica:** Circumplex Model of Affect (Russell, 1980), com 2 eixos — valência (positivo↔negativo) e arousal/energia (ativo↔calmo). Fornece justificativa estabelecida em pesquisa de emoção musical para o mapeamento, em vez de uma escolha arbitrária.

**Vocabulário curado** (não texto livre — evita a necessidade de NLP, que o dataset atual não suporta bem):

| Palavra (chip) | Âncora aproximada no espaço |
|---|---|
| Energético | energy alto, valence alto |
| Feliz/Alegre | valence alto, energy médio |
| Dançante | danceability alto |
| Calmo/Relaxante | energy baixo, acousticness alto |
| Melancólico | valence baixo, energy baixo |
| Intenso/Raivoso | valence baixo, energy alto |
| Instrumental/Foco | instrumentalness alto, speechiness baixo |
| Acústico | acousticness alto, energy médio-baixo |

**Calibração com dado real:** as âncoras acima são pontos de partida, a serem ajustados com o MTG-Jamendo (subset `autotagging_moodtheme`, 18.486 faixas com tags de mood atribuídas por humanos). Extraindo `energy`/`valence` (via Essentia) das faixas tagueadas `happy`, `sad`, `energetic`, `calm` etc., os valores médios reais substituem os números estimados da tabela — um uso pontual do Jamendo, apenas para calibração, sem precisar integrar o catálogo inteiro ao produto final.

## 4. Clustering

- **Gaussian Mixture Model**, não K-Means puro — dado o silhouette baixo observado no EDA (0,15–0,23 conforme o conjunto de features), fronteiras ambíguas entre estilos são a norma, não exceção. GMM fornece uma probabilidade de pertencimento por faixa em vez de atribuição rígida, mais compatível com o que os dados mostram e mais útil para ranqueamento (uma faixa pode "meio-servir" a um mood).
- `K` entre 8 e 12 (testado no Passo 5.4 do EDA).
- Cada faixa recebe um score de proximidade a cada palavra do vocabulário, não apenas um rótulo de cluster único.

## 5. Seleção de candidatas dado o mood escolhido — Concluído, ver `entregas/modelo_mood_clustering.ipynb`

- O usuário escolhe uma ou mais palavras (ex: "Calmo" + "Instrumental").
- O sistema calcula o ponto-alvo como a média das âncoras das palavras escolhidas, no espaço das **6 features** validadas na Seção 2 (atualizado — o texto original desta seção mencionava 7, desatualizado após a correção de rumo da seleção de features).
- `sklearn.neighbors.NearestNeighbors` (distância euclidiana, mesma métrica usada na atribuição de mood por faixa) retorna as N faixas mais próximas — desempenho adequado em memória para 113 mil faixas × 6 dimensões, sem necessidade de índice vetorial dedicado (Faiss ou similar seria excessivo nessa escala).
- Implementado como a função `selecionar_candidatas(palavras, n)`, validada com o exemplo desta própria seção ("Calmo" + "Instrumental" → mistura equilibrada das duas palavras) e um teste de consistência (pedir 1 palavra isolada concorda 100% com o mood já atribuído àquela faixa). Detalhes em `decisoesEJustificativasModelo.md` e `roteiroModelo.md`.

## 6. Sequenciamento (transições suaves) — Concluído, ver `entregas/sequenciamento_playlist.ipynb`

**Nearest-neighbor ambicioso** sobre o conjunto de candidatas — parte de uma faixa, sempre avança para a vizinha ainda não usada de menor custo de transição, combinando distância de audio features + proximidade de `tempo` + compatibilidade de `key`/`mode` via **Camelot Wheel** (técnica de mixagem harmônica usada por DJs).

**Resultado real:** ambicioso entrega 10,5 BPM de salto médio de tempo e 72% de transições harmonicamente compatíveis, contra 20,6 BPM e 18% do aleatório (mesmo conjunto de candidatas) — melhoria clara e robusta à escolha dos pesos (testado em 6 combinações).

**Achado não previsto no plano original, encontrado durante a implementação:** 9,4% dos `track_id` únicos do catálogo são a mesma música sob um `track_id` diferente (edições/compilações distintas — casos extremos como faixas natalinas chegam a 30-45 `track_id`). Não detectado por nenhuma checagem de duplicata do EDA. Exigiu deduplicar candidatas por `(track_name, artists)`, não só `track_id` — sem essa correção, uma playlist de teste repetiu a mesma música 9 vezes. Decisões e o erro corrigido documentados em `decisoesEJustificativasSequenciamento.md` e `roteiroSequenciamento.md`.

## 7. Avaliação

Não há gabarito objetivo no dataset para "transição suave" ou "mood correto" (ver `decisoesEJustificativasEDA.md` e `guidingQuestions.md`) — a avaliação principal é **qualitativa**: gerar playlists de teste e avaliar por escuta (ex: "a transição soou natural?", "o resultado bateu com o mood pedido?"). Como métrica auxiliar (fraca, mas útil para comparar versões do próprio algoritmo entre si): distância média entre faixas consecutivas da sequência gerada — menor distância indica maior suavidade *pela definição do próprio algoritmo*, não uma prova de qualidade musical percebida.

## 8. Interface — Concluído, ver `entregas/interface_playlist.ipynb` e artifact publicado

**Implementada como um mapa de mood real (energia × valência), não a grade de chips do mockup original** — os 8 moods posicionados nas coordenadas exatas das âncoras da Fase 2, seleção de até 3 por clique, com o centroide (ponto-alvo real do algoritmo) desenhado ao vivo. Consome `playlists_precomputadas.json` (92 combinações de 1-3 palavras pré-computadas com `gerar_playlist`, sem backend em tempo real) e mostra BPM + código Camelot por faixa, tornando visível o próprio critério de sequenciamento da Fase 3.

**Publicado em:** https://claude.ai/code/artifact/5b12e6f2-b61a-4332-9545-cf0638572400 — decisões completas em `decisoesEJustificativasInterface.md` e `roteiroInterface.md`.

**Ficou fora, deliberadamente:** os controles secundários do mockup abaixo (duração, faixa-semente, variedade/previsibilidade) não têm função real implementada no motor — incluí-los seria decoração enganosa. Ficam como escopo futuro. O mockup original é preservado abaixo como registro histórico do design inicial.

Seleção por chips (multi-select), não texto livre — pelos motivos técnicos descritos na Seção 3.

**Os 8 chips já não são especulativos** — são o vocabulário final, implementado e validado em `modelo_mood_clustering.ipynb`, com a contagem real de faixas do catálogo (113.549) atribuída a cada um (`catalogo_com_mood.parquet`):

| Mood | Faixas | % do catálogo |
|---|---:|---:|
| Energético | 18.925 | 16,7% |
| Instrumental | 17.724 | 15,6% |
| Intenso | 16.078 | 14,2% |
| Feliz | 14.992 | 13,2% |
| Calmo | 14.192 | 12,5% |
| Melancólico | 13.818 | 12,2% |
| Dançante | 9.021 | 7,9% |
| Acústico | 8.799 | 7,7% |

```
┌─────────────────────────────────────────────┐
│  Que clima você quer pra sua playlist?       │
│                                               │
│  [ Energético ]  [ Feliz ]  [ Dançante ]     │
│  [ Calmo ]  [ Melancólico ]  [ Intenso ]     │
│  [ Instrumental ]  [ Acústico ]              │
│                                               │
│  (selecionados: Calmo, Instrumental)         │
│                                               │
│  Duração aproximada: [====●=====] 45 min     │
│                                               │
│  [ Gerar playlist ]                          │
└─────────────────────────────────────────────┘
```

- **8 chips, fixos** — não é mais uma faixa "6 a 8" especulativa, é o vocabulário definitivo do modelo (responde à guiding question de Usuário sobre quantidade de opções: 8 está dentro da faixa recomendada de UX para seleção múltipla).
- **Multi-select**, permitindo combinar até 2-3 palavras (o ponto-alvo é a média das âncoras escolhidas) — mecanismo ainda não implementado (Seção 5, pendente).
- **Desbalanceamento a considerar na interface:** `Dançante` e `Acústico` têm quase metade das faixas de `Energético`/`Instrumental` (9 mil vs. 17-19 mil) — não é um problema de cobertura (ainda são milhares de faixas), mas vale evitar prometer "variedade infinita" igualmente para todos os chips, ou sinalizar isso de alguma forma sutil na UI.
- Controles secundários opcionais: duração da playlist, faixa-semente inicial (conecta com a guiding question de Usuário sobre música inicial), alternância entre "mais variedade" e "mais previsível".
- O design é compatível tanto com uma tela dedicada quanto com um fluxo de chat (o bot pergunta o mood e apresenta os chips como botões de resposta rápida) — a lógica por trás não muda entre os dois formatos.

## Roadmap resumido

| Fase | Escopo | Status |
|---|---|---|
| 1. Catálogo + features | EDA completo, dados limpos e validados | Concluído (semanas 1-2) |
| 2. Vocabulário de mood + clustering | Calibração das âncoras com MTG-Jamendo, treino do GMM | Concluído — ver `entregas/modelo_mood_clustering.ipynb`, roteiro em `roteiroModelo.md` |
| 3. Sequenciamento | Lógica nearest-neighbor ambicioso + tempo/key | Concluído — ver `entregas/sequenciamento_playlist.ipynb`, roteiro em `roteiroSequenciamento.md` |
| 4. Interface | Chips de seleção + geração de playlist | Concluído — ver `entregas/interface_playlist.ipynb`, artifact publicado, roteiro em `roteiroInterface.md` |
| 5. Avaliação | Testes qualitativos de escuta | Planejado |

## Fase 2 — Resumo do que foi implementado

- **Calibração externa real:** 25 shards (4.866 faixas) dos descritores AcousticBrainz/Essentia do MTG-Jamendo foram baixados e cruzados com as tags de mood humanas. Confirmou-se, com fonte de dados independente do catálogo Spotify, que `loudness`/`danceability` diferenciam mood de forma clara e ordenada, enquanto `tempo`/`dissonance` quase não variam entre tags — o mesmo padrão já encontrado de forma independente no Passo 5.4 do EDA (validação cruzada entre duas fontes de dados distintas).
- **Seleção de features validada para a tarefa (correção de rumo):** a escolha inicial de 7 features reaproveitava o η² de ANOVA calculado no EDA para `track_genre` — um critério validado para gênero, não para mood. Corrigido com filtro de redundância (correlação) + método wrapper (K-Means/silhouette) comparando 6 subconjuntos candidatos, restrito aos que preservam a capacidade de diferenciar as 8 palavras do vocabulário. Resultado: 6 features (`energy`, `valence`, `danceability`, `acousticness`, `instrumentalness`, `speechiness`, sem `loudness`) — melhor silhouette que o conjunto original (0,2216 vs. 0,1993). Decisões detalhadas em `decisoesEJustificativasModelo.md`.
- **Vocabulário de 8 palavras** (`Energetico`, `Feliz`, `Dancante`, `Calmo`, `Melancolico`, `Intenso`, `Instrumental`, `Acustico`), ancorado em quantis reais da distribuição do catálogo, não em valores arbitrários.
- **GMM (K=8)** treinado sobre as 113.549 faixas — o BIC não indicou um K estatisticamente ótimo (continuou caindo até K=30 testado), então K foi fixado por necessidade de produto (tamanho do vocabulário), decisão documentada explicitamente no notebook.
- **Correção de design durante a implementação:** rotular clusters do GMM por palavra mais próxima cobriu só 4 das 8 palavras — corrigido classificando cada faixa individualmente pela âncora mais próxima (nearest-anchor), garantindo cobertura completa do vocabulário.
- **Erro de calibração encontrado e corrigido na validação qualitativa:** a âncora original de `Melancolico` capturava metal/industrial (só valência baixa, energia moderada) em vez de música triste e calma — corrigido ao exigir também energia baixa. Validado com um exemplo real reconhecível (*"Something In The Way"*, Nirvana, tornou-se o resultado mais próximo da âncora).
- Artefatos salvos para reuso nas próximas fases: `entregas/modelo_mood.joblib` (transformadores + GMM + âncoras) e `entregas/catalogo_com_mood.parquet` (catálogo com mood atribuído por faixa).

## Riscos conhecidos (herdados do EDA e da avaliação de viabilidade)

- Silhouette baixo (0,15–0,23): clusters não têm fronteira nítida; o GMM mitiga isso parcialmente ao expor probabilidade em vez de atribuição rígida — mas a atribuição de mood final usa distância direta por faixa (nearest-anchor), não o cluster do GMM, evitando herdar essa fragilidade na etapa que mais importa para o produto.
- Nenhuma fonte de dados aberta disponível hoje fornece sequências reais de playlist como gabarito (o Spotify Million Playlist Dataset não está mais disponível para download público) — a definição de "transição suave" é necessariamente uma heurística de engenharia, não um padrão aprendido de dados reais.
- `energy` e `valence` são parcialmente independentes (correlação 0,26) — o espaço de mood não pode ser reduzido a uma única dimensão.
- Nenhum descritor de baixo nível testado (Spotify ou Essentia) mede valência diretamente — o eixo positivo/negativo do vocabulário depende inteiramente da variável `valence` do Spotify (um modelo proprietário, não auditável), sem validação externa independente equivalente à obtida para o eixo de energia/arousal.
