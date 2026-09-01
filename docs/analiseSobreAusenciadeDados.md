# Como decidir o tratamento de valores ausentes em colunas numéricas

## 1. Primeiro passo: entender o mecanismo da ausência

Antes de escolher uma técnica, a literatura de estatística (classificação de Rubin, 1976 — ainda é o framework padrão hoje) separa a ausência de dado em três categorias, porque cada uma justifica uma abordagem diferente:

- **MCAR (Missing Completely At Random):** a ausência não tem relação com nenhuma variável, nem com o próprio valor que falta. Ex: um sensor que falha aleatoriamente por interferência elétrica. É o cenário "mais seguro" — qualquer técnica tende a não introduzir viés sistemático.
- **MAR (Missing At Random):** a ausência está relacionada a outras colunas observadas, mas não ao valor ausente em si. Ex: faixas de podcasts têm mais chance de não ter `danceability` calculada — isso está ligado à coluna `track_genre` (observável), não ao valor de danceability que faltou.
- **MNAR (Missing Not At Random):** a ausência está ligada ao próprio valor que falta. Ex: se faixas muito pouco populares tendem a não ter `popularity` registrada — o motivo da ausência é justamente o valor baixo que ela teria. Esse é o cenário mais perigoso, porque qualquer imputação tende a enviesar o resultado sistematicamente.

Na prática, raramente se prova isso com certeza estatística — mas dá pra investigar por evidência indireta (o que foi feito com o `time_signature == 1` no notebook de EDA: checar se a anomalia se concentra em algum subgrupo específico, como um gênero).

## 2. Técnicas — divididas em dois grupos

### A) Deleção

- **Listwise (remover a linha inteira):** o que foi feito na linha com nome de artista/álbum/faixa ausente no dataset Spotify. Só é uma boa escolha quando: (1) a proporção de linhas afetadas é pequena (regra prática comum: <5% dos dados), e (2) há evidência de que é MCAR ou MAR-fraco. Se for uma fração grande, ou se estiver correlacionada com alguma variável relevante (MNAR), remover introduz viés — um tipo de registro está sendo sistematicamente excluído, não uma amostra aleatória.
- **Pairwise (usar só o que está disponível, por cálculo):** por exemplo, ao calcular uma correlação entre duas colunas, usar apenas as linhas onde ambas estão presentes, mesmo que outras linhas do dataset tenham ausência em outra coluna qualquer. Preserva mais dado, mas pode gerar inconsistência (cada estatística calculada sobre uma base de linhas ligeiramente diferente).

### B) Imputação (substituir por um valor estimado)

Da mais simples para a mais sofisticada:

1. **Substituição por medida central (média/mediana):** simples, mas tem um efeito colateral sério — reduz artificialmente a variância da coluna e enfraquece qualquer correlação que ela tenha com outras variáveis, pois o mesmo valor é inserido repetidamente onde antes havia variação real. Aceitável só quando a proporção ausente é muito pequena.
2. **Imputação por subgrupo:** em vez da média global, usar a média/mediana do grupo relevante. Por exemplo, se `danceability` estivesse ausente em algumas linhas, faria mais sentido preencher com a mediana de `danceability` daquele `track_genre` do que a mediana global — porque músicas do mesmo gênero tendem a ser mais parecidas entre si do que a média geral do dataset. É uma melhoria direta sobre a técnica 1, sem muito mais complexidade.
3. **Imputação baseada em modelo:**
   - **KNN Imputer:** para cada linha com valor ausente, encontra as *K* linhas mais parecidas (com base nas outras colunas) e usa a média/mediana dos vizinhos. Captura relações mais ricas do que só "gênero".
   - **Imputação por regressão:** treina um modelo simples (ex: regressão linear) para prever a coluna ausente a partir das outras colunas, usando as linhas completas como treino.
   - **MICE (Multiple Imputation by Chained Equations):** a técnica mais robusta estatisticamente — gera múltiplas versões imputadas do dataset (não uma só), captura a incerteza da imputação, e depois combina os resultados. É o "padrão-ouro" em pesquisa estatística séria, mas é mais custoso e complexo de justificar num projeto introdutório.
4. **Flag de ausência + imputação:** além de preencher o valor, criar uma coluna binária extra (ex: `danceability_ausente = True/False`). Isso é importante especialmente sob suspeita de MNAR: mesmo que seja necessário "inventar" um valor pra manter a linha, o próprio fato de ter faltado pode carregar informação relevante, e essa coluna permite que um modelo aprenda isso separadamente.
5. **Deixar como está (não imputar):** alguns modelos — inclusive o LightGBM — lidam nativamente com valores ausentes (`NaN`) durante o treino, decidindo a melhor forma de dividir cada nó da árvore considerando os dados ausentes como uma categoria própria. Nesse caso, imputar manualmente pode até ser desnecessário ou contraproducente — vale checar se a ferramenta usada depois já resolve isso internamente antes de aplicar uma técnica de imputação por conta própria.

## 3. Como decidir, na prática

| Pergunta | Direciona para |
|---|---|
| Poucas linhas afetadas (~<5%) e parece aleatório? | Deleção listwise |
| Ausência concentrada num subgrupo identificável (ex: um gênero)? | Imputação por subgrupo, ou investigar se é MNAR antes |
| Coluna muito importante pra análise final? | Técnica mais robusta (KNN/regressão/MICE), não média simples |
| O modelo final já lida com `NaN` nativamente (ex: LightGBM, XGBoost)? | Pode nem precisar imputar |
| Suspeita de MNAR (ausência ligada ao próprio valor)? | Cuidado redobrado — qualquer imputação tende a enviesar; documentar a limitação é mais honesto do que "resolver" |

## 4. Aplicação ao caso do dataset Spotify

Neste dataset, a decisão foi trivial: a coluna ausente era texto identificador (não é possível estimar um nome de artista) e afetava apenas 1 linha em 114 mil — deleção listwise é claramente a escolha correta. Um cenário mais delicado seria, por exemplo, `danceability` ausente em 2.000 linhas espalhadas por vários gêneros, o que exigiria a análise mais cuidadosa descrita acima antes de decidir entre deleção e imputação.
