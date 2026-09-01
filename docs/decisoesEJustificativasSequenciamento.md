# Decisões e Justificativas — Fase 3 (Sequenciamento por Transição Suave)

Este documento registra cada decisão metodológica tomada em `entregas/sequenciamento_playlist.ipynb` e a justificativa por trás dela, no mesmo formato de `decisoesEJustificativasEDA.md` e `decisoesEJustificativasModelo.md`. Inclui um erro real cometido e corrigido durante a própria implementação.

## Compatibilidade harmônica

**Decisão:** usar a roda de Camelot (mapeamento fixo `key`+`mode` → posição numerada 1-12 com sufixo A/menor ou B/maior) para medir compatibilidade entre tonalidades.
**Justificativa:** é a notação padrão usada por DJs profissionais para mixagem harmônica — não precisa ser aprendida a partir dos dados, é uma tabela de consulta fixa e bem estabelecida. `key`/`mode` já estavam disponíveis e completos no catálogo (Passo 1 do EDA), sem necessidade de nova coleta.

**Decisão:** três níveis de penalidade harmônica — 0,0 (tonalidade idêntica), 0,15 (relativa maior/menor ou vizinha na roda), 0,5 (incompatível) — em vez de uma regra binária compatível/incompatível.
**Justificativa:** a roda de Camelot já distingue graus de compatibilidade (idêntica > relativa/vizinha > distante); colapsar isso em binário perderia informação que o próprio sistema de referência (usado por DJs) considera relevante.

## Algoritmo de sequenciamento

**Decisão:** nearest-neighbor ambicioso (parte de uma faixa, sempre avança para a candidata não usada de menor custo) em vez de uma solução ótima global (ex: caixeiro-viajante exato).
**Justificativa:** o plano (`planejamentoModelo.md`, Seção 6) já previa essa abordagem como "tratável para o escopo do projeto" — encontrar a sequência de custo mínimo globalmente é NP-difícil; ambicioso é O(n²) e simples de implementar/explicar, adequado para dezenas de faixas por playlist (não milhares).

**Decisão:** combinar três termos no custo de transição (distância de audio features + diferença de `tempo` normalizada + penalidade harmônica), com pesos padrão `peso_tempo=0,5` e `peso_harmonico=1,0`.
**Justificativa:** os pesos foram testados em 6 combinações diferentes (incluindo zerar cada termo individualmente) antes de fixar um padrão — o resultado (`delta_tempo` entre 4,6 e 7,1 BPM, `compat` entre 79% e 83% em todas as combinações testadas, contra a mesma faixa `~18 BPM`/`~40%` do aleatório) mostrou que o algoritmo é **robusto à escolha exata dos pesos**, não sensível a um ajuste fino específico. Isso reduz o risco de overfitting os pesos a um exemplo específico sem dado real de validação (ver limitação sobre ausência de gabarito de transição, já registrada em `planejamentoModelo.md`).

## Deduplicação (erro cometido e corrigido)

**Decisão original (revertida):** deduplicar as candidatas retornadas pela busca de vizinhos apenas por `track_id`.
**Por que foi revertida — erro real encontrado na validação:** a primeira versão da função `selecionar_candidatas` retornou 30 candidatas para `Energetico` com **30 `track_id` únicos**, mas ao inspecionar a playlist gerada, a música "Happier" (Marshmello;Bastille) aparecia **9 vezes**, e "Suena El Dembow" **7 vezes** — cada ocorrência com um `track_id` diferente. Medido no catálogo inteiro: **9,4% dos `track_id` únicos são a mesma música (`track_name`+`artists` idênticos) sob um `track_id` diferente** — provavelmente edições/compilações diferentes do mesmo lançamento no catálogo do Spotify (casos extremos: faixas natalinas com 30-45 `track_id` diferentes, reeditadas anualmente). Esse tipo de duplicata nunca tinha sido checado no EDA (Passo 2.2 cobriu linha idêntica e `track_id` repetido em gênero diferente, não título+artista repetido sob `track_id` novo) — descoberta registrada retroativamente em `decisoesEJustificativasEDA.md`.

**Decisão final:** deduplicar por `(track_name, artists)`, buscando um excedente de vizinhos (`n × 6` em vez de `n`) para garantir candidatas suficientes após remover as repetições.
**Justificativa:** para um caso de uso que apresenta faixas individuais a um usuário final (uma playlist), o que importa é "não repetir a mesma música", não "não repetir o mesmo `track_id`" — são critérios diferentes, e o catálogo tem uma fração não-desprezível (9,4%) de casos onde eles divergem.

## Validação

**Decisão:** comparar as métricas de suavidade (delta médio de `tempo`, % de transições harmonicamente compatíveis) da ordem ambiciosa contra a média de 20 embaralhamentos aleatórios das mesmas candidatas, em vez de reportar só o número absoluto do algoritmo ambicioso.
**Justificativa:** um número absoluto (ex: "10,5 BPM de salto médio") não diz se é bom ou ruim sem uma referência — o baseline aleatório usa exatamente o mesmo conjunto de faixas, isolando o efeito da ordenação em si.

**Decisão:** reportar os números finais (10,5 BPM / 72% ambicioso vs. 20,6 BPM / 18% aleatório) mesmo sendo piores que os números do teste inicial com o bug de duplicação (4,6-6,9 BPM / 79-83%), em vez de manter o resultado "bonito" anterior.
**Justificativa:** os números anteriores estavam inflados artificialmente — faixas duplicadas (mesma música) têm distância ~0 entre si, tornando a "transição" trivialmente suave sem representar nenhuma qualidade real do algoritmo. Reportar o número pior, mas correto, é mais importante do que reportar o número melhor, mas enganoso.

## Limitações registradas (não resolvidas, apenas documentadas)

- A validação de suavidade usa métricas **auto-referenciadas** (definidas pelo próprio critério que o algoritmo otimiza) — confirma que o ambicioso é consistentemente melhor que aleatório dentro da própria definição de "suave", não que a suavidade resultante realmente soa bem para um ouvinte humano (limitação já registrada em `planejamentoModelo.md`: não existe gabarito de transição real disponível).
- A deduplicação por `(track_name, artists)` usa correspondência exata de texto — variações de grafia, remixes com nome ligeiramente diferente, ou featurings listados em ordem diferente entre `track_id` não seriam detectados como a "mesma música". Não medido nem corrigido nesta fase.
- Os pesos `peso_tempo`/`peso_harmonico` foram validados como robustos *dentro da faixa testada* (0,0 a 1,0) e para uma única palavra de mood (`Energetico`) — não testado para todas as 8 palavras nem para consultas multi-palavra.
