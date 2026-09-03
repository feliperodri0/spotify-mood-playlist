# Análise crítica do projeto

Documento de crítica ao próprio projeto, escrito depois de ler o código, os artefatos salvos e os notebooks — não apenas a documentação. Onde a crítica contradiz o que está escrito em outro documento daqui, a evidência citada (arquivo e linha) é a fonte.

O objetivo não é listar tudo que poderia existir num mundo ideal, e sim separar: **o que está genuinamente bom**, **o que está quebrado ou frágil**, e **o que falta para isso ser um projeto de Sistemas de ML** e não apenas uma boa análise de dados com um produto acoplado.

---

## 1. A questão central: existe modelo neste projeto?

**Resposta curta: quatro objetos foram ajustados aos dados, mas nenhum deles decide o comportamento do produto.**

O que está salvo em `entregas/modelo_mood.joblib`:

| Objeto | Tamanho | É "modelo treinado"? | É usado no produto? |
|---|---|---|---|
| `NearestNeighbors` | **12,33 MB** | Não — índice de busca, guarda os dados | **Sim** |
| `PowerTransformer` | ~0,00 MB | Parcialmente — aprende λ (Yeo-Johnson) | Sim |
| `StandardScaler` | ~0,00 MB | Parcialmente — aprende média/desvio | Sim |
| `GaussianMixture(K=8)` | ~0,00 MB | **Sim** — EM, parâmetros aprendidos | **Não** |

Duas observações desconfortáveis saem dessa tabela:

1. **Os 12,33 MB do "modelo" são o catálogo memorizado**, não parâmetros aprendidos. O arquivo é grande porque guarda os dados, não porque aprendeu algo.
2. **A única coisa que é genuinamente um modelo treinado (o GMM) nunca é lida pelo produto.** `PipelineMood.__init__` (`produto/motor_playlist.py:53-59`) carrega `power_transformer`, `scaler`, `knn`, `features`, `cols_assimetricas`, `vocab_df` e `vocab_X` — e pula `modelo["gmm"]`. Confirmado: `grep -rn "gmm" produto/` retorna zero ocorrências.

O que de fato decide o comportamento:

- **Mood de cada faixa** — uma regra determinística, não um modelo:
  `df['mood'] = vocab_df.index[cdist(X, vocab_X).argmin(axis=1)]` (`modelo_mood_clustering.ipynb`, célula 20).
- **As 8 âncoras do vocabulário** — quantis do próprio catálogo escritos à mão (p10/p25/p50/p75/p90), célula 11. Nenhuma foi aprendida.
- **Sequenciamento** — algoritmo ambicioso com dois pesos fixados à mão (`peso_tempo=0.5`, `peso_harmonico=1.0`, `motor_playlist.py:102`).

**Conclusão:** o sistema é *recuperação + regras*. Isso não é um defeito em si — é, aliás, a escolha tecnicamente correta dada a ausência de rótulo (§2). O defeito é de **nomenclatura e de honestidade do artefato**: um arquivo chamado `modelo_mood.joblib`, contendo um GMM que não faz nada, comunica algo que não é verdade para quem só olha o repositório de fora.

### Por que não treinar foi a decisão certa

Está documentado em `planejamentoModelo.md` §7 e nos riscos conhecidos, e a justificativa se sustenta:

- O dataset **não tem rótulo de mood** nem sequências reais de playlist.
- O Spotify Million Playlist Dataset (que daria sequências reais como gabarito) saiu do ar.
- O endpoint `audio-features` da API do Spotify foi descontinuado para novos apps (nov/2024), impedindo enriquecimento.

Sem variável-alvo, não há aprendizado supervisionado. Treinar um classificador para prever o mood atual seria **circular**: ele aprenderia a imitar `argmin(cdist(...))`, uma função que já é exata, instantânea e explicável. Trocaria-se uma regra perfeita por uma aproximação dela.

### Onde treinar teria valido a pena (e não foi feito)

Esta é a crítica mais dura do documento, porque **o rótulo humano estava dentro do repositório e não foi usado para treinar nada**:

- `dados_externos/mtg_jamendo/moodtheme_tags.tsv` (1,8 MB, versionado) contém **tags de mood anotadas por humanos**. O MTG-Jamendo foi usado apenas para *calibração descritiva* — comparar médias de `avg_loudness`/`danceability` entre grupos de tags (célula 3-4).
- Com esse mesmo dado dava para treinar um **classificador supervisionado real** (features acústicas → tag de mood) e transferi-lo para o catálogo Spotify, gerando um mood aprendido de julgamento humano em vez de derivado de quantis arbitrários.
- Isso teria resposta direta para a limitação mais séria registrada no próprio projeto: *"nenhum descritor de baixo nível mede valência diretamente"*. Um modelo treinado em tags humanas aprende valência **indiretamente**, por correlação com o que humanos chamam de `sad`/`happy` — exatamente o que a abordagem por quantis não consegue fazer.

O segundo caso legítimo seria **aprender a função de custo do sequenciamento** (learning-to-rank sobre transições reais) em vez de fixar `0.5` e `1.0` à mão.

---

## 2. O que está genuinamente bom

Sendo justo antes de criticar — há trabalho sério aqui, e ele não é comum:

- **Rastreabilidade de decisão.** Cada fase tem um par `roteiro*.md` / `decisoesEJustificativas*.md` com o *porquê*, não só o *o quê*. Isso é raro e é o maior ativo do projeto.
- **Erros próprios documentados em vez de escondidos.** A âncora de `Melancolico` recalibrada após validação qualitativa; a rotulagem por cluster substituída por classificação por faixa; o bug de deduplicação. Todos registrados com o número antes/depois.
- **O achado de duplicatas é um trabalho de dados de verdade.** Descobrir que ~9,4% do catálogo são a mesma música sob `track_id` diferente ("Happier" aparecendo 9 vezes numa playlist de 30) é o tipo de defeito que só aparece quando se olha a saída de perto — e a correção foi retroalimentada no documento do EDA como limitação não capturada originalmente.
- **Seleção de features com critério de produto sobrepondo a métrica.** O método wrapper apontou `E_minimalista` (silhouette 0,2438) como melhor, e a escolha foi `C_sem_loudness` (0,2216) porque as opções melhores **quebravam o vocabulário** (sem `valence` não dá para separar `Feliz` de `Melancolico`). Escolher a segunda melhor métrica por uma razão explícita de produto é maturidade, não erro.
- **Convergência independente de duas fontes.** O padrão "`loudness`/`danceability` fortes, `tempo` fraco" apareceu tanto no η² do catálogo Spotify quanto na calibração MTG-Jamendo. Validação cruzada real entre datasets distintos.
- **Baseline honesto.** O sequenciamento foi comparado com ordem aleatória (10,5 vs 20,6 BPM; 72% vs 18% de compatibilidade harmônica), e os números **pioraram** quando as duplicatas foram removidas — e isso foi registrado como "agora são honestos" em vez de ficar com o número inflado.

---

## 3. Problemas críticos

### 3.1 A avaliação principal do projeto nunca foi feita — ALTA

O próprio `planejamentoModelo.md` §7 define: *"a avaliação principal é **qualitativa**: gerar playlists de teste e avaliar por escuta"*. Isso **não aconteceu**. `roteiroInterface.md` registra a Fase 5 como pendente até hoje.

O problema não é apenas "faltou uma etapa". É que **todas as métricas existentes são autorreferenciais**: Δ BPM médio e % de transições compatíveis são exatamente os termos que a função de custo do sequenciamento minimiza. Medir o algoritmo com a régua que ele próprio otimiza garante um bom número e não prova nada sobre qualidade percebida. O documento reconhece isso ("métrica auxiliar (fraca…)"), mas reconhecer não substitui fazer.

**Correção mínima viável:** 5–10 pessoas, teste cego, 3 playlists de 10 faixas por pessoa — (a) sequenciada pelo algoritmo, (b) ordem aleatória, (c) ordenada só por BPM crescente. Perguntar qual soou mais coesa. Isso é um fim de semana de trabalho e transformaria a única afirmação não sustentada do projeto em resultado.

### 3.2 O GMM é peso morto dentro do artefato — ALTA

Um modelo treinado, salvo e distribuído que nenhum código lê. Além de comunicar algo falso sobre o projeto, é dívida: quem for manter vai gastar tempo entendendo um componente que não faz nada.

**Duas saídas legítimas, escolha uma:**
- **Usar:** `cluster_prob` (a probabilidade da atribuição, já calculada e salva em `catalogo_com_mood.parquet`) é um sinal de confiança pronto e ignorado. Daria para filtrar faixas ambíguas ou expor "quão típica dessa vibe" a faixa é.
- **Remover:** tirar o GMM do joblib e renomear o arquivo para algo honesto (`indice_mood.joblib`), deixando o notebook manter a análise de clustering como exploração documentada.

### 3.3 O produto gera a mesma playlist para sempre — ALTA (produto)

`motor_playlist.py:114`: `visitado, atual, restante = [0], 0, set(range(1, n))`. A sequência **sempre começa pela candidata de índice 0** (a mais próxima da âncora), e todo o resto é determinístico. Mesmo mood + mesmo N ⇒ playlist byte a byte idêntica, sempre.

Para um produto cujo nome é "playlists automáticas, feitas pra você", isso é um defeito de conceito: o usuário pede de novo e recebe exatamente a mesma coisa. Não há motivo para voltar.

**Correção:** semente aleatória na faixa inicial, ou amostrar N entre as top-2N candidatas, ou deixar o usuário escolher a faixa-semente (isso já estava previsto no mockup original e foi cortado por não existir no motor — ver `decisoesEJustificativasInterface.md`, "o que foi deixado de fora").

### 3.4 Os pesos da função de custo são arbitrários — MÉDIA

`peso_tempo=0.5, peso_harmonico=1.0` não vieram de lugar nenhum. A documentação diz que o resultado é "robusto à escolha exata dos pesos" — o que também significa, lido ao contrário, que **não há evidência de que esses pesos sejam bons**, apenas de que o resultado não é sensível a eles. Robustez a um parâmetro é frequentemente sinal de que o parâmetro não está fazendo muito trabalho.

**Correção:** varredura de pesos avaliada contra o teste de escuta de §3.1 — sem o teste humano, não há como calibrar isso de forma não-circular.

### 3.5 `popularity` é ignorada por completo — MÉDIA

`grep -rn "popularity" produto/` retorna zero. É a única coluna do dataset que carrega qualquer sinal de aceitação humana, e não entra em nenhuma decisão. O resultado é que uma playlist pode ser inteiramente composta de faixas obscuras que ninguém reconhece — o que, para um produto de recomendação, é um problema sério de percepção de qualidade, independente da coesão acústica.

**Correção:** usar como desempate ou como filtro suave (ex.: exigir percentil mínimo de popularidade entre as candidatas, ou ponderar a distância por popularidade).

### 3.6 Acoplamento por ordem de linha entre dois artefatos — MÉDIA

`motor_playlist.py:64`: `assert (df_clean["track_id"].values == mood_df["track_id"].values).all()`.

O `assert` está certo e existe porque um bug real de `merge` já corrompeu 113.549 linhas em 183.265 uma vez. Mas ele trata o sintoma: o design continua exigindo que **dois arquivos separados estejam na mesma ordem de linha**, uma invariante que nada garante além da disciplina de quem roda os notebooks na ordem certa.

**Correção:** um único artefato com as colunas de mood já embutidas, ou merge explícito por chave única (com verificação de cardinalidade).

### 3.7 O projeto não registra nada — ALTA (estratégica)

Este é o ponto que amarra todos os outros. A justificativa central para não treinar um modelo é **"não existe rótulo"**. Só que o produto construído é exatamente o instrumento capaz de produzir rótulo — e ele não guarda absolutamente nada:

- Quais combinações de mood foram pedidas.
- Quais prévias viraram playlist de verdade no YouTube (**sinal implícito forte de aprovação**).
- Quais faixas o usuário teria removido, se pudesse.

Sem instrumentação, o projeto está travado permanentemente no estado "não dá para treinar por falta de dado" — sendo que gerar esse dado custa um arquivo de log com três campos. **É o item de maior alavancagem do documento inteiro:** é o que transformaria um sistema de regras num sistema que pode aprender.

---

## 4. Engenharia: o gap mais visível para uma residência de *Sistemas* de ML

O projeto tem qualidade de **análise** alta e maturidade de **engenharia de sistema** baixa. Para a disciplina em questão, essa é a inversão mais problemática.

| Falta | Impacto |
|---|---|
| `requirements.txt` / `pyproject.toml` | Ninguém consegue reproduzir o ambiente. O README manda instalar 9 pacotes por `pip install` solto, sem versão. |
| Qualquer teste automatizado | Zero arquivos de teste no repositório. Bugs reais e graves já ocorreram (duplicatas, corrupção por merge, busca escalonada) — todos encontrados por inspeção manual, nenhum teria sido pego de novo numa regressão. |
| CI | Nenhum. Nada valida que os notebooks ainda rodam. |
| Versionamento de artefato adequado | 20 MB de `dataset.csv` + ~26 MB de artefatos derivados (`.parquet`, `.joblib`) versionados no git. Artefato derivado em git é anti-padrão — deveria ser reproduzível pelos notebooks ou ficar em Git LFS/DVC. |
| Separação treino/serviço | O `PipelineMood` carrega 113.549 linhas + transforma o catálogo inteiro **a cada boot** do Flask. Funciona local; não é um desenho de serviço. |

Um teste que teria evitado dois dos três bugs históricos cabe em dez linhas:

```python
def test_playlist_nao_repete_musica():
    p = pipeline.gerar_playlist(["Energetico"], n=30)
    assert len(p) == 30
    assert p.duplicated(subset=["track_name", "artists"]).sum() == 0
```

---

## 5. Riscos conceituais que continuam de pé

- **`valence` é a base de metade do vocabulário e é um modelo proprietário não auditável do Spotify.** O projeto registra isso como risco conhecido — corretamente — mas segue dependendo inteiramente dele, sem mitigação. `Feliz` vs `Melancolico` é, na prática, "o que o modelo fechado do Spotify acha que é feliz". Treinar em tags do Jamendo (§1) seria a mitigação real.
- **A deduplicação por `(track_name, artists)` pode colapsar gravações legitimamente diferentes** (estúdio vs. ao vivo, versão vs. remix com mesmo título). O ganho supera a perda, mas a perda nunca foi medida.
- **Escopo do produto oscilou muito** (Spotify → abortado → YouTube; front-end criado → excluído → recriado; quatro iterações de redesign visual). Sinal de que "pronto" nunca foi definido antes de começar. Custo real em retrabalho.

---

## 6. Prioridades sugeridas

Ordenadas por (impacto ÷ esforço), não por dificuldade:

1. **Instrumentar o produto** (§3.7) — 1 arquivo de log, 3 campos. Destrava todo o resto, incluindo a possibilidade futura de treinar de verdade.
2. **Fazer o teste de escuta** (§3.1) — um fim de semana. É a única evidência que falta para as afirmações centrais do projeto pararem de ser autorreferenciais.
3. **Resolver o GMM** (§3.2) — usar `cluster_prob` como sinal de confiança, ou remover e renomear o artefato. Uma hora de trabalho, elimina a maior incoerência entre o que o repositório diz e o que ele faz.
4. **Quebrar o determinismo do sequenciamento** (§3.3) — poucas linhas, muda a percepção do produto de "demo" para "coisa que se usa".
5. **`requirements.txt` + os 3 testes óbvios** (§4) — meio dia, e é literalmente o tema da disciplina.
6. **Treinar o classificador de mood no MTG-Jamendo** (§1) — o item mais caro e o mais interessante. Transformaria o projeto de "sistema de regras" em "sistema de ML" de verdade, com rótulo humano, usando dado que já está no repositório.

---

## 7. Veredito

O projeto é **honesto, bem documentado e tecnicamente defensável** naquilo que escolheu fazer. A decisão de não treinar um modelo supervisionado está correta e bem justificada pela ausência de gabarito — não é uma desculpa, é uma leitura acertada do problema.

Os três problemas reais são:

1. **O artefato mente pelo nome** — chama-se "modelo", tem um modelo dentro, e o modelo não faz nada.
2. **A avaliação que o próprio projeto definiu como principal nunca foi executada** — restando apenas métricas que medem o algoritmo com a régua dele mesmo.
3. **O projeto justifica não aprender pela falta de dado, e simultaneamente não coleta o dado que o desbloquearia** — sendo que já tem em mãos, versionado e não usado para isso, o único conjunto de rótulos humanos que precisaria (MTG-Jamendo).

Nenhum dos três é caro de resolver. O primeiro é uma hora, o terceiro começa com um arquivo de log, e o segundo é o mais valioso de todos.
