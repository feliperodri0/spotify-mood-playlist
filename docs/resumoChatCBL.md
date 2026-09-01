# Resumo do Projeto — CBL Sistemas de Machine Learning (Spotify Dataset)

## Contexto
Projeto CBL (Challenge Based Learning) da disciplina Sistemas de Machine Learning, na fase **Investigate** (Aula 4). Uso do **Spotify Tracks Dataset** (~114.000 faixas), com colunas de audio features (danceability, energy, valence, acousticness, instrumentalness, liveness, speechiness, tempo, loudness, key, mode), `popularity`, `track_genre`, `explicit`, entre outras.

**Fontes gratuitas do dataset:**
- Kaggle (original, maharshipandya): kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset
- Kaggle (114k, priyamchoksi): kaggle.com/datasets/priyamchoksi/spotify-dataset-114k-songs
- Hugging Face (sem login): huggingface.co/datasets/maharshipandya/spotify-tracks-dataset

**Limitação crítica identificada:** o dataset é um **snapshot** — não tem coluna de data/release_date nem série temporal de popularidade.

---

## Ideia inicial (descartada): influência de filmes na popularidade

**Objetivo de negócio proposto:** reduzir incerteza em decisões de investimento em sincronização midiática (música em filme), aumentando ROI do budget de marketing musical.

**Objetivo de ML proposto:** prever se vale investir numa associação musica-filme.

### Por que foi considerada inviável
1. **Sem dado temporal**: impossível medir "popularidade antes vs. depois" do lançamento do filme só com esse dataset.
2. **Causalidade reversa**: estúdios tendem a escolher músicas *já populares* para trilha sonora — o modelo aprenderia correlação, não causa.
3. **Amostra pequena**: poucas músicas com sincronização documentada em filme, dentro de 114k faixas — problema de classe rara.
4. **Restrição adicional da API do Spotify**: desde 27/11/2024, novos apps perderam acesso a endpoints como `audio-features`, `audio-analysis`, `recommendations` e `related-artists`; em maio/2025 o acesso estendido passou a exigir 250k usuários mensais ativos — dificultando ainda mais buscar audio features novas via API.

---

## Ideias alternativas levantadas
1. **Motor de busca por "mood" para sincronização musical** ← escolhida
2. Diagnóstico de "por que essa música é popular" (explicabilidade via SHAP/feature importance)
3. Detecção de inconsistência de gênero / qualidade dos dados (auto-tagging e correção de catálogo)

---

## Ideia escolhida: Motor de busca por mood/atmosfera musical

**Conceito:** em vez de prever causalidade (inviável), construir uma ferramenta que ajuda um music supervisor a **encontrar** músicas com o perfil sonoro certo para uma cena/campanha — sem depender de dados temporais.

**Abordagem técnica:**
- Clustering (K-means/HDBSCAN) sobre as audio features do dataset → cria "arquétipos sonoros" (ex: "tensão crescente", "nostálgico-acústico", "euforia")
- Classificador supervisionado usando `track_genre` como rótulo de apoio
- Reposicionamento de escopo: não é "produto comercial inédito" (já existem soluções como Cyanite, Musiio, Songtradr), e sim **prova de conceito open-source/de baixo custo** de uma capacidade hoje restrita a ferramentas pagas — com foco extra em explicabilidade (por que cada cluster se formou), o que os produtos comerciais (caixa-preta, treinados em áudio bruto) não oferecem.

### O que o dataset atual já resolve
- Clustering e classificação por gênero — 114k faixas é volume suficiente
- Todas as audio features necessárias já estão presentes

### O que precisaria ser adicionado
| Necessidade | Motivo | Fonte sugerida |
|---|---|---|
| Vocabulário de mood validado | Evitar nomear clusters de forma arbitrária | **MTG-Jamendo** (subset `autotagging_moodtheme`) |
| Validação externa dos clusters | Confirmar que os clusters batem com percepção humana | Mesmo dataset, usado só para comparação |
| Preview de áudio / capa | Dataset só tem números, sem áudio para o usuário ouvir | Spotify Web API `search`/`track` (endpoints `search` e `track` ainda ativos, diferente de `audio-features`) |
| Busca temática por letra (opcional) | Busca por tema, não só som | Genius API |
| Deduplicação | Mesma música aparece com `track_id` diferente em vários gêneros | ETL próprio (não precisa de fonte nova) |

### Sobre o MTG-Jamendo Dataset
- Dataset aberto de auto-tagging musical (Bogdanov et al., 2019), construído com faixas do Jamendo sob licença Creative Commons
- Mais de 55.000 faixas de áudio completas, com 195 tags entre categorias de gênero, instrumento e mood/theme
- **Subset relevante para o projeto: `autotagging_moodtheme`** — 56 classes balanceadas (ex: `action`, `epic`, `energetic`, `melancholic`, `deep`, `uplifting`)
- Repositório oficial: `github.com/MTG/mtg-jamendo-dataset` (splits prontos em `data/splits/split-0/`)
- **Importante:** não dá pra fazer join direto por `track_id` com o dataset do Spotify (fontes diferentes). Uso correto: treinar/validar um classificador de mood separadamente no MTG-Jamendo e usá-lo como "gabarito" para checar se os clusters do dataset do Spotify fazem sentido musicalmente — não como fonte de dados unificada.

---

## Guiding Questions levantadas (por categoria)

### Dados
- O que significa cada coluna? (atividade: pesquisar fonte original)
- Os 114 gêneros com exatamente 1.000 registros cada indicam dataset artificialmente balanceado — isso reflete a distribuição real de streams do Spotify?
- Removendo faixas com popularidade zero, os rankings mudam muito?
- Há duplicatas (mesma música em múltiplos gêneros com `track_id` diferente)?
- Quais colunas precisam de normalização antes de treinar?

### Usuário
- Quem usaria o modelo (music supervisor, gravadora, estúdio)? Que decisão essa pessoa toma com a saída do modelo?
- Faz mais sentido segmentar por características de áudio do que por gênero?
- O usuário confiaria numa saída binária ou precisa de explicação dos fatores?
- Qual o custo de um erro para esse usuário?

### Modelo
- Quais modelos podem ser criados com base nesse dataset? (chatbot, recomendação, clustering)
- Como o Spotify usa esses dados para recomendar músicas (filtragem colaborativa + content-based + NLP)?
- É melhor modelar como classificação ou regressão?
- Como validar os clusters sem um "gabarito" externo?

### Produção ML
- Com que frequência o modelo precisaria ser retreinado?
- Se a fonte de dados externa mudar de estrutura, o pipeline quebra?
- Qual a escala esperada de uso (10 ou 10 mil consultas/dia)?

### Ética
- Há questões de direitos autorais nos dados de músicas e artistas?
- Dados de artistas menores/independentes estão sub-representados?
- Um modelo que prioriza "hits" pode reforçar a exclusão de artistas independentes?
- Há transparência suficiente sobre por que o modelo recomendou algo?

---

## Sobre recomendação musical do Spotify (contexto de pesquisa)
O sistema real combina:
1. **Filtragem colaborativa** (peso maior): comportamento coletivo usuário-faixa
2. **Análise de áudio (content-based)**: resolve cold start de músicas novas — é a parte que o dataset do Spotify Tracks Dataset consegue simular
3. **NLP**: varre conteúdo editorial/blogs para associar gêneros e "vibes"
Pipeline em estágios: retrieval de candidatos → ranking → re-ranking com diversidade. Sinais comportamentais como saves/adição a playlist pesam positivo; skip antes de 30s pesa negativo.

---

## Próximos passos sugeridos
1. Fazer EDA (deduplicação, distribuição de popularidade, balanceamento de gênero)
2. Rodar clustering piloto com as audio features
3. Baixar o subset `autotagging_moodtheme` do MTG-Jamendo e definir estratégia de validação cruzada de vocabulário
4. Fechar as 5-7 guiding questions oficiais do grupo com atividade/recurso/responsável/prazo
5. Preencher o canvas: objetivo de negócio (reposicionado como PoC acessível) + objetivo de ML + escopo em uma frase (TRATA/NÃO TRATA)
