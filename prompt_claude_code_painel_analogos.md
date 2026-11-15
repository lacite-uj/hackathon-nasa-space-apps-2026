# Prompt para o Claude Code — Painel de análogos (lista lateral + foco no globo + card)

> Cole tudo abaixo no Claude Code, na raiz do repositório, na branch atual.

---

## 1. Contexto

Estou no NASA Space Apps 2026, no desafio *"Identify Earth Locations that Analog the Permanent Moon Base
Locations and Mars"*. O repositório tem:

- um ETL Python (`etl/`) que gera `web/data/analogs.json` (contrato v2) a partir das planilhas da equipe:
  **14 análogos na Terra** × **2 alvos** (Lua – polo sul/Shackleton e Marte – Jezero) = **28 links**;
- um front estático em Three.js (`web/`) que hoje só desenha os três globos (Lua à esquerda, Terra no centro,
  Marte à direita) e os marcadores (`web/src/main.js`, `web/src/globe.js`). Ainda não existem arcos, clique,
  seleção nem painel. `web/index.html` já tem placeholders escondidos: `#panel`, `#site-list` e `#legend`.

**Antes de começar, leia** `CLAUDE.md`, `docs/instrucoes-desenvolvimento.md` (as seções 3 e 5 em especial),
`etl/analogs.schema.json` e o `web/data/analogs.json` real.

**Objetivo desta tarefa:** um painel para explorar os análogos. Uma **lista lateral** com os locais. Ao
clicar num local, o globo **foca** no ponto e abre um **card** com a análise: por que o local é análogo,
como ele pontua e **onde a analogia falha**.

Sou estudante de Sistemas de Informação e quero aprender com o processo. Explique as decisões conforme
avança e **me pergunte** quando algo for ambíguo, em vez de supor. Comece com um plano curto (arquivos,
módulos, estado da seleção) e espere meu ok antes de codar.

## 2. Mudança de desenho em relação ao doc

O doc (seção 5, "Painel lateral") previa um painel lateral com os detalhes do link. **O desenho agora é
outro:**

- **painel lateral (esquerda)** = a lista de locais, que também resolve a "lista acessível" da seção 5;
- **card (direita)** = os detalhes do local selecionado.

Atualize `docs/instrucoes-desenvolvimento.md` (seções 1, 5 e 7) para refletir isso. O conteúdo exigido
para os detalhes continua o mesmo da seção 5.

## 3. Regras que não mudam

- O front **não calcula semelhança**. Todo número exibido vem do JSON (`adherence`, `score`, `rank`,
  `dimensions`, `utilities`…). Formatar é permitido (ex.: `1,54/3`, `1º de 14`); recalcular, não.
- `adherence: null` / `status: "a_medir"` aparecem como **"a medir"**, nunca como 0. Uma categoria ausente
  em `dimensions` também é "a medir".
- "Limitações universais" (`in_score: false`) aparece **separada**, marcada como fora da nota.
- **"Onde a analogia falha" (`limits`) fica sempre visível**, nunca dentro de algo recolhido por padrão.
  O desafio exige isso.
- Sem framework e sem build: JS puro em módulos ES, Three.js 0.160.0 pelo import map que já existe e CSS
  no `index.html` ou num `.css` em `web/`. Precisa rodar com `cd web && python -m http.server 8000` e na
  Vercel estática.
- Não mude o formato do `analogs.json`. Se faltar algum dado, **me pergunte** antes. Mudar o contrato
  exige atualizar o ETL, o schema, o `SCHEMA.md` e o doc.
- Textos da interface em português do Brasil, com números no formato pt-BR (vírgula decimal).

## 4. O que construir

### 4.1 Painel lateral — lista de locais (`#site-list`)

- No topo, um **seletor de alvo `Lua | Marte`**, que começa em Marte.
- Os 14 análogos aparecem **ordenados pelo `rank` do link com o alvo ativo**. Cada item mostra a posição,
  o nome, o país, uma mini barra de aderência (largura = `score`) e a aderência (`1,5`).
- Marcas discretas no item:
  - o local foi **listado** pela equipe para esse alvo (`listed_as` contém o alvo);
  - o local tem coordenada aproximada (`approximate_coords`).
- Ao trocar o alvo, a lista reordena. Se houver um local selecionado, ele continua selecionado.
- O item selecionado fica destacado. Ao passar o mouse sobre um item, o marcador correspondente no globo é
  destacado (e vice-versa, se não ficar caro).
- Acessibilidade: é uma lista navegável por teclado (setas para mover, `Enter` para selecionar, `Esc` para
  limpar), com `aria-selected` no item ativo e foco visível.

### 4.2 Foco no globo (ao selecionar um local, pela lista ou pelo 3D)

1. A **Terra gira suavemente** (slerp de quaternion, ~600 ms) até o análogo ficar de frente para a câmera.
2. A **câmera se aproxima da Terra** num zoom moderado. O globo do alvo ativo precisa continuar visível,
   porque ele também entra em foco. Ao fechar o card, a câmera volta ao enquadramento dos três globos
   (o cálculo atual em `resize()`).
3. O **globo do alvo da aba ativa do card** (Lua ou Marte) gira até o alvo ficar de frente, e **um arco**
   liga o análogo ao alvo. Use `Line2`/`LineMaterial` dos addons, com largura e cor pelo `score` do link,
   como diz a seção 5 do doc. Atualize as pontas do arco a cada frame, sem recriar a geometria. Trocar a
   aba troca o arco e o globo em foco.
   - Só o arco do link ativo. Desenhar a rede inteira (28 arcos) fica **fora do escopo** desta tarefa,
     mas deixe `arcs.js` pronto para isso.
4. Os **outros marcadores esmaecem** (opacidade ~0,15) e um **anel de destaque** aparece em volta do
   análogo e do alvo.
5. **Clique no 3D:** `Raycaster` nos marcadores da Terra. Hover mostra um tooltip com o nome, e o clique
   faz a mesma seleção da lista. Clicar num alvo (Lua/Marte) troca o seletor da lista para aquele alvo.
   Clicar no vazio ou apertar `Esc` limpa a seleção.
6. Durante a animação, o `OrbitControls` não pode brigar com ela. Desative o controle ou interpole o
   `target` e a posição, e devolva o controle ao usuário no fim.
7. Respeite `prefers-reduced-motion`: sem animação, o foco salta direto para a posição final.

Um único módulo de estado (ex.: `selection.js`) guarda `{ analogId, targetId }` e notifica a lista, o card
e a cena. Lista, card e 3D não conversam entre si diretamente. As regras de sincronia estão em 4.4.

### 4.3 Card de detalhes (`#panel`, flutuante à direita)

O card **não é modal**: não escurece o fundo nem bloqueia o globo, que continua girável. Tem um botão ✕ e
fecha com `Esc`. Com rolagem interna, o cabeçalho e as abas ficam fixos no topo.

**Cabeçalho:** nome (`full_name`), país, lote (`batch`), aviso de coordenada aproximada se houver.

**Abas `Lua | Marte`:** são o mesmo controle do seletor da lista, não um estado separado (ver 4.4).
- A aba ativa é sempre o `targetId` da seleção, ou seja, o mesmo alvo da lista.
- A aba do alvo listado pela equipe (`listed_as`) tem a marca "listado". Se o card estiver no outro alvo,
  mostre uma linha discreta: *"A equipe listou este local como análogo da Lua"*, com um link que troca
  para aquela aba.
- Trocar a aba troca o alvo da seleção inteira: a lista reordena, o arco muda e o globo em foco muda.

**Conteúdo da aba (link `analog × target`), nesta ordem:**

1. **Por que é análogo:** `description` e `clipping` do análogo (recorte usado) e `data_notes`, se houver.
2. **Veredito:** aderência `X,XX / 3`, posição `Nº de 14` e `best_in_network_count` ("melhor da rede em N
   utilidades").
   - Se `matches_listing` for `false`, mostre um aviso claro, não como erro. Exemplo: *"A equipe listou
     este local como análogo da Lua, mas o modelo indica Marte."* Isso acontece de verdade: os 4 locais
     listados para a Lua têm aderência maior a Marte.
   - Dê contexto para a escala: a maior aderência da rede fica perto de 1,5/3. Mostrar o `rank` junto
     evita que 1,1 pareça "nota baixa" sem referência.
3. **Por categoria:** uma barra por `dimensions` (nota 0–3 e "`evaluated` de `total` utilidades"), na
   ordem de `data.dimensions`. "Limitações universais" vai separada, como fora da nota.
4. **Pontos fortes** (`strengths`).
5. **Onde a analogia falha** (`limits`), sempre aberta.
6. **Ainda a medir** (`to_measure`).
7. **Utilidades** (`utilities`), agrupadas por categoria: nome, nota ou "a medir", selo "melhor da rede"
   (`best_in_network`) e o texto `reading`, quando existir. Hoje só os 3 locais da base têm `reading`; não
   deixe espaço vazio nos outros. Esta seção pode começar recolhida.
8. **Uso na exploração** (`exploration_use`).
9. **Fontes** (`sources`), com links (`target="_blank" rel="noopener"`). Hoje vêm de 9 a 31 fontes por
   link (parecem ser as da planilha inteira, não só do local). Mostre recolhido, com a contagem.
   **Me avise** se confirmar que são as da planilha toda, porque isso pode ser ajuste no ETL.

### 4.4 Sincronia entre lista, card e globo

Existe **um só alvo ativo** (`targetId`). Ele define, ao mesmo tempo, a ordem da lista, a aba do card, o
arco e o globo do alvo em foco. Lista e card nunca mostram alvos diferentes.

| Ação do usuário | `analogId` | `targetId` |
|---|---|---|
| Clica num item da lista | o item | **não muda** (o usuário já escolheu o alvo na lista) |
| Clica num análogo no 3D | o marcador | o alvo para o qual o local foi listado (`listed_as`); se foi listado para os dois, não muda |
| Clica num alvo no 3D (Lua/Marte) | não muda | o alvo clicado |
| Troca o seletor da lista ou a aba do card | não muda | o alvo escolhido |
| `Esc`, ✕ ou clique no vazio | `null` | não muda |

Quando o `targetId` muda e há um local selecionado, a lista reordena com uma animação curta (ou sem
animação, com `prefers-reduced-motion`), mantém o item selecionado destacado e o rola até ele ficar visível
(`scrollIntoView({ block: 'nearest' })`), sem roubar o foco do teclado.

### 4.5 Celular (largura < 768 px)

- A lista vira uma barra superior recolhível ou um botão "Locais", e o card vira uma **gaveta embaixo**
  (~60% da altura, arrastável ou com botão de expandir).
- Sem rolagem horizontal na página e com alvos de toque ≥ 44 px.
- Os globos ficam menores, e o foco continua funcionando.

## 5. Arquivos esperados

Siga a estrutura da seção 2 do doc:

- `web/src/selection.js`: estado da seleção e eventos;
- `web/src/interaction.js`: raycasting, hover, clique, tooltip;
- `web/src/focus.js` (ou dentro de `main.js`, se ficar pequeno): animação de rotação e câmera;
- `web/src/arcs.js`: arco entre corpos (`Line2`), já preparado para a rede completa;
- `web/src/list.js`: painel lateral;
- `web/src/panel.js`: card;
- `web/src/format.js`: formatação pt-BR, "a medir" e rótulos.

Mantenha `main.js` como orquestrador e reaproveite `latLonToVector3`, `addMarker` e `MARKER_COLORS` de
`globe.js`.

## 6. Critérios de pronto

- [ ] Abre com `python -m http.server` **sem erros nem avisos no console**.
- [ ] Os 14 locais aparecem na lista, ordenados pelo `rank` do alvo ativo, e a ordem bate com o JSON.
- [ ] Clicar num item (ou num marcador, ou dar `Enter` pelo teclado) gira a Terra até o local, gira o
      alvo, desenha o arco, esmaece o resto, aproxima a câmera e abre o card.
- [ ] Lista e card mostram sempre o mesmo alvo: trocar a aba reordena a lista, e trocar o seletor da lista
      troca a aba, mantendo o local selecionado visível. Clicar num análogo no 3D segue a tabela da 4.4.
- [ ] O aviso de `matches_listing` aparece nos 4 locais listados para a Lua.
- [ ] Nenhum número na tela é calculado no front, e "a medir" nunca aparece como 0.
- [ ] "Onde a analogia falha" está visível sem nenhum clique extra.
- [ ] `Esc`, o ✕ e o clique no vazio limpam a seleção e devolvem a câmera ao enquadramento inicial.
- [ ] Os testes de lat/lon com `?debug=1` continuam caindo no lugar certo.
- [ ] Funciona a 375 px de largura (lista recolhida, card em gaveta, sem rolagem horizontal).
- [ ] `docs/instrucoes-desenvolvimento.md` atualizado com o novo desenho (lista à esquerda, card à direita).
- [ ] `.venv/bin/python -m pytest` continua passando (o ETL não deve mudar nesta tarefa).

Ao terminar, me mostre como testar (passos no navegador) e liste o que ficou de fora ou em aberto.
