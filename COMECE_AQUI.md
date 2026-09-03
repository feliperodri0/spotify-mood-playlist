# Comece aqui

Documento único de reorientação. Se você (ou alguém do grupo) abriu este repositório e não sabe por onde começar, leia **só este arquivo**. Ele explica o que o projeto faz, como funciona, em que pé está e onde procurar detalhe — sem jargão.

Os 13 documentos em `docs/` continuam valendo como memória detalhada de cada decisão. Este aqui existe para você não precisar atravessar todos eles para se localizar.

---

## 1. O que é

Você escolhe até 3 palavras de clima (`Feliz`, `Calmo`, `Intenso`...) e o sistema devolve uma playlist onde as músicas combinam entre si, **na ordem certa para ouvir em sequência** — e cria essa playlist de verdade na sua conta do YouTube.

A base é o Spotify Tracks Dataset: 114.000 faixas, 113.549 depois da limpeza.

---

## 2. Como funciona, em 3 passos

### Passo 1 — Cada música tem um "endereço"

Cada faixa tem 6 números que descrevem seu som:

`energia` · `felicidade (valence)` · `dançabilidade` · `quão acústica` · `quão instrumental` · `quanta voz falada`

Pense num mapa: cada uma das 113.549 músicas ocupa um ponto nesse espaço de 6 dimensões.

> Por que esses 6, e não os 9 disponíveis? Foram testados 6 conjuntos diferentes, medindo qual separava melhor as músicas. Detalhe em `docs/decisoesEJustificativasModelo.md`.

### Passo 2 — Cada palavra de clima também tem um endereço

As 8 palavras do vocabulário têm um ponto-alvo **definido à mão** nesse mesmo mapa, usando estatísticas do próprio catálogo. Exemplo:

- `Feliz` = felicidade no topo 10% + energia no topo 25%
- `Calmo` = energia nos 25% mais baixos + acústica no topo 25%

Quando você escolhe palavras, o sistema calcula o ponto médio entre elas e busca as músicas mais próximas desse ponto.

**É aqui que mora a decisão principal do sistema** — e ela é uma regra escrita à mão, não um modelo que aprendeu sozinho. Isso é deliberado (ver §4).

### Passo 3 — A ordem das músicas

Com as faixas escolhidas, o sistema as ordena para que faixas seguidas tenham **BPM parecido** e **tonalidades compatíveis** (roda de Camelot, técnica que DJs usam para mixar sem dissonância). A regra é simples: começa numa faixa e sempre pega a próxima mais parecida.

**Funciona, e foi medido:** salto médio de 10,5 BPM entre faixas (contra 20,6 numa ordem aleatória) e 72% de transições harmonicamente compatíveis (contra 18%).

---

## 3. Onde está cada coisa

```
entregas/          A entrega formal: 4 notebooks, na ordem
  1. eda_spotify.ipynb              → análise dos dados, limpeza
  2. modelo_mood_clustering.ipynb   → as 8 palavras e o mapa (Passos 1 e 2 acima)
  3. sequenciamento_playlist.ipynb  → a ordem das músicas (Passo 3)
  4. interface_playlist.ipynb       → junta tudo numa função só
  + os arquivos .parquet/.joblib que esses notebooks geram

produto/           O MVP funcional (fora do escopo formal da entrega)
  motor_playlist.py          → o motor: escolhe as faixas + ordena
  youtube_playlist_oauth.py  → cria a playlist de verdade no YouTube
  app_local/                 → interface web, roda no seu computador

docs/              O porquê de cada decisão (13 arquivos, ver §6)
```

**Para rodar o produto:**
```bash
cd produto/app_local
../../.venv/bin/python app.py
```
Depois abra `http://localhost:5001`.

---

## 4. A pergunta que sempre volta: "existe um modelo treinado aqui?"

**Resposta curta: não existe um modelo que decida algo.** Vale entender o porquê, porque é a decisão mais importante do projeto.

### Por que não foi treinado um modelo

Para treinar um modelo supervisionado, você precisa de **gabarito** — exemplos onde alguém já disse a resposta certa. E aqui não existe:

- O dataset **não tem** uma coluna dizendo "esta música é melancólica".
- Não existe base pública com **sequências reais de playlist** para ensinar o que é uma "transição boa" (o Spotify Million Playlist Dataset saiu do ar).
- A API do Spotify que forneceria mais dados foi descontinuada para apps novos em nov/2024.

Sem gabarito, não há o que aprender. Por isso a decisão foi construir uma regra explícita e auditável em vez de um modelo. **Essa escolha está certa** e está documentada em `docs/planejamentoModelo.md` §7.

### Então por que existe um GMM treinado no arquivo?

Porque **o plano original era outro**, e ele foi testado e descartado — corretamente:

1. **Ideia inicial:** agrupar as 113 mil músicas em 8 grupos automaticamente (isso é o GMM), batizar cada grupo com um nome de clima e devolver músicas do grupo pedido.
2. **O que a implementação mostrou:** os grupos que o algoritmo formou sozinho **não eram climas**. Eram aglomerados sem fronteira nítida (silhouette 0,15–0,23, baixo), e a métrica BIC não apontou um número ideal de grupos. Chamar "grupo 3" de `Melancolico` seria uma decisão arbitrária sua, não uma descoberta do algoritmo.
3. **A correção:** trocar a pergunta. Em vez de *"em que grupo essa música caiu?"*, passou a ser *"de qual das 8 âncoras que eu defini ela está mais perto?"* — direto, explicável faixa a faixa, sem herdar a fragilidade dos grupos mal separados.

O GMM **continuou salvo dentro de `modelo_mood.joblib` por descuido** — já estava treinado, faz parte da exploração documentada no notebook, e ninguém o removeu na hora de salvar. Nenhuma linha do produto o lê (`grep -rn "gmm" produto/` retorna zero).

**Isso não é um erro de raciocínio — é falta de limpeza.** O incômodo real é de nome: um arquivo chamado `modelo_mood.joblib`, que contém um modelo que não faz nada, comunica algo falso para quem olha o repositório de fora. Dos seus 12,33 MB, 12,33 MB são o índice de busca (o catálogo memorizado); o GMM ocupa praticamente zero.

### E o que tem de machine learning, então?

Tem, mas em papel de apoio, não decidindo:

- **k-NN** (busca por vizinhos mais próximos) — é aprendizado baseado em instâncias, e é o que entrega as faixas.
- **PowerTransformer / StandardScaler** — ajustados aos dados para deixar as 6 dimensões comparáveis entre si.
- **Seleção de features por método wrapper**, medindo qualidade de agrupamento.
- **GMM com seleção de K por BIC** — feito, avaliado, descartado com justificativa.

O que **não** existe é uma função de decisão aprendida. Quem decide o clima de cada faixa é a regra do Passo 2.

---

## 5. Em que pé está

**Funcionando:**
- Os 4 notebooks rodam e geram os artefatos.
- O produto local gera playlists e cria de verdade no YouTube (login OAuth testado e confirmado).
- Limite de 30 faixas por playlist, calculado a partir da cota da API do YouTube (cada faixa custa 150 unidades das 10.000 diárias gratuitas).

**Pendente / conhecido:**
- **A avaliação principal nunca foi feita.** O plano define que a validação real é por escuta humana — e isso não aconteceu. As métricas atuais (Δ BPM, % compatível) medem o algoritmo com a régua que ele próprio otimiza.
- **O GMM morto** ainda está no arquivo salvo.
- **A playlist é sempre idêntica** para o mesmo pedido (o sequenciamento começa sempre pela mesma faixa).
- **Sem `requirements.txt`, sem testes automatizados.**

Lista completa e priorizada em `docs/analiseCritica.md`.

**Os 3 próximos passos que valem mais que o resto:**

1. **Limpar o GMM** — remover do `.joblib` e renomear para `indice_mood.joblib`. ~10 minutos, elimina a maior fonte de confusão do projeto.
2. **Teste de escuta** — 5 pessoas, playlist do algoritmo vs. ordem aleatória, qual soou mais coesa. Não exige código nenhum e é o que falta para as afirmações centrais deixarem de ser autorreferenciais.
3. **Um `requirements.txt` e 3 testes básicos** — meio dia, e é justamente o tema da disciplina (Sistemas de ML).

---

## 6. Onde procurar detalhe (só quando precisar)

Cada fase tem um par de documentos: **roteiro** (o que foi feito, passo a passo) e **decisõesEJustificativas** (por que foi feito assim).

| Se você quer saber... | Leia |
|---|---|
| Como a ideia do projeto surgiu e o que foi descartado | `docs/resumoChatCBL.md` |
| As perguntas norteadoras do CBL, respondidas | `docs/guidingQuestions.md` |
| Como os dados foram limpos e o que foi encontrado | `docs/roteiroEDA.md` + `docs/decisoesEJustificativasEDA.md` |
| O plano geral do modelo (visão de cima) | `docs/planejamentoModelo.md` |
| Como as 8 palavras e o mapa foram construídos | `docs/roteiroModelo.md` + `docs/decisoesEJustificativasModelo.md` |
| Como a ordem das músicas foi definida e validada | `docs/roteiroSequenciamento.md` + `docs/decisoesEJustificativasSequenciamento.md` |
| Histórico da interface e do produto | `docs/roteiroInterface.md` + `docs/decisoesEJustificativasInterface.md` |
| Crítica ao projeto, problemas e prioridades | `docs/analiseCritica.md` |
| Por que faltam dados e o que isso limita | `docs/analiseSobreAusenciadeDados.md` |

---

## 7. As 3 coisas para levar na cabeça

1. **O sistema é um mapa + uma régua + uma regra de ordenação.** Não tem modelo decidindo nada, e isso é proposital: não existe gabarito para aprender.
2. **O GMM foi um caminho testado, medido, descartado com razão — e esquecido dentro do arquivo.** É limpeza pendente, não erro conceitual.
3. **O que falta de mais importante não é mais código: é o teste de escuta.** Sem ele, a afirmação "as transições são suaves" se apoia só na métrica que o próprio algoritmo otimiza.
