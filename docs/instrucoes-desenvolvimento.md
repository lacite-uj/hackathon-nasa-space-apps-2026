# Instruções de desenvolvimento — Visualizador de análogos Terra · Lua · Marte

Projeto para o desafio **Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars**
(NASA Space Apps 2026, 14–15/11/2026).
Documento do desafio: https://claude.ai/artifact/CEd5y9NhnDyDDwbRRJTuE1
Página oficial: https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/

## 1. O que vamos construir

Uma página web com três globos 3D (Terra, Lua e Marte) que mostra os análogos terrestres de locais
candidatos na Lua e em Marte e explica por que eles se parecem e onde a analogia falha.

- **Layout:** a Terra fica grande no centro, com a Lua e Marte como globos menores dos lados.
- **Locais:** os dois alvos — Lua (polo sul, Shackleton) e Marte (cratera Jezero) — aparecem como pontos
  nos globos deles. Os 14 análogos na Terra também são pontos.
- **Painel lateral (esquerda):** a lista dos 14 análogos, com um seletor de alvo `Lua | Marte`, ordenada
  pelo `rank` do link com o alvo ativo. É também a lista acessível (teclado) do projeto.
- **Seleção:** ao clicar num local (na lista ou no globo), a Terra gira até ele, o globo do alvo ativo gira
  até o alvo, a câmera enquadra os dois e um **arco** liga o análogo ao alvo. A espessura e a cor do arco
  mostram a aderência do análogo àquele alvo.
- **Card (direita):** os detalhes do local selecionado para o alvo ativo: por que é análogo, a aderência
  por categoria de utilidade (Engenharia, Ciência, Recursos, Pouso e mobilidade, Operações humanas e
  Limitações universais) e por utilidade (U01–U19), os pontos fortes e onde a analogia falha.
- **Rede completa (próxima fase):** os 28 arcos (14 × 2 ligações) desenhados ao mesmo tempo. Hoje aparece só
  o arco do link ativo; `web/src/arcs.js` já aceita uma lista de links.

O desafio exige dizer **onde a analogia falha**. O card precisa mostrar isso sempre visível, não só os
pontos fortes.

## 2. Arquitetura

```
planilhas da equipe (data/raw/*.xlsx)
        │  python -m etl build
        ▼
ETL Python (etl/) ──gera──▶ data/processed/  (tabelas normalizadas, CSV, relatório de validação)
                  └─gera──▶ web/data/analogs.json  ──lido por──▶  web/index.html (Three.js)
```

- **Python** faz toda a análise: lê as planilhas do modelo de aderência, recalcula todas as notas com a
  mesma lógica das fórmulas do Excel, confere o resultado célula a célula com o Excel e escreve os JSON.
- **Front-end** é estático: um HTML que carrega Three.js e lê o JSON. Não há back-end.
- O front-end não calcula semelhança. Se um número aparece na tela, ele veio do JSON.
- **Deploy de testes:** Vercel, como site estático. O `vercel.json` publica só a pasta `web/`, sem build.
  O ETL não roda na Vercel: gere o `analogs.json` localmente e commite. Cada branch ou PR ganha uma
  URL de preview (ver README).

### Estrutura de pastas

```
.
├── etl/                      # Python: ETL das planilhas
│   ├── __main__.py           # CLI: python -m etl build | check
│   ├── config.py             # ids estáveis, aliases, conjuntos de critérios e decisões de modelagem
│   ├── text.py               # slugs, aliases, números em pt-BR, códigos de fonte
│   ├── extract.py            # lê as abas (openpyxl, valores em cache do Excel)
│   ├── transform.py          # normaliza em tabelas longas (locais, critérios, valores...)
│   ├── scoring.py            # o modelo de aderência (fórmulas na docstring)
│   ├── validate.py           # compara o recalculado com o cache do Excel, célula a célula
│   ├── site.py               # monta o web/data/analogs.json
│   ├── load.py               # grava data/processed/ e o JSON do site
│   ├── analogs.schema.json   # JSON Schema do analogs.json
│   └── SCHEMA.md             # dicionário de dados de data/processed/
├── tests/                    # pytest (regras do modelo + regressão com as planilhas)
├── data/
│   ├── raw/                  # planilhas da equipe (fora do git; copie antes de rodar o ETL)
│   └── processed/            # saída do ETL (fora do git; regenerável)
├── web/
│   ├── index.html
│   ├── styles.css            # todo o CSS (lista, card, legenda, celular)
│   ├── src/
│   │   ├── main.js           # orquestrador: cena, câmera, render loop, liga os módulos ao estado
│   │   ├── globe.js          # criação de um globo, marcadores, anel de destaque, conversão lat/lon
│   │   ├── selection.js      # estado da seleção { analogId, targetId } e eventos
│   │   ├── focus.js          # animação de rotação dos globos e da câmera
│   │   ├── arcs.js           # arcos entre corpos (Line2)
│   │   ├── interaction.js    # raycasting, hover, clique, tooltip
│   │   ├── list.js           # painel lateral: seletor de alvo e lista de locais
│   │   ├── lightbox.js       # modal da foto ampliada
│   │   ├── resize-panels.js  # bordas arrastáveis da lista e do card
│   │   ├── panel.js          # card de detalhes
│   │   ├── format.js         # formatação pt-BR, "a medir" e rótulos
│   │   └── dom.js            # criação de elementos sem innerHTML
│   ├── textures/             # earth.jpg, moon.jpg, mars.jpg
│   ├── images/analogs/       # foto de cada local (crédito em etl/config.py › IMAGENS)
│   └── data/analogs.json     # gerado pelo ETL (vai pro git: é o que a Vercel publica)
└── docs/
```

## 3. Contrato de dados: `analogs.json` (versão 2)

Este arquivo é a fronteira entre Python e front-end. Mudanças nele precisam ser combinadas entre os dois lados
e refletidas em `etl/analogs.schema.json`. Os ids são os mesmos de `data/processed/`
(`analogs[].id` = `local_id`, `targets[].id` = `alvo_id`, `utilities[].id` = `U01`…`U19`).

```json
{
  "version": 2,
  "generated_at": "2026-11-15T12:00:00Z",
  "model": { "name": "Base de referência v1.1 – 14/11/2026", "data_date": "2026-11-14",
             "scale": "Aderência de 0 a 3 ...; score = aderência ÷ 3", "excluded_from_score": ["limitacoes-universais"] },
  "dimensions": [
    { "id": "engenharia", "label": "Engenharia", "in_score": true },
    { "id": "limitacoes-universais", "label": "Limitações universais", "in_score": false }
  ],
  "targets": [
    { "id": "marte", "body": "mars", "name": "Marte – Jezero", "short_name": "Jezero",
      "lat": 18.38, "lon": 77.58, "description": "Tem rover em solo...", "clipping": "Cratera Jezero e seu delta" }
  ],
  "analogs": [
    { "id": "haughton", "name": "Haughton", "full_name": "Haughton", "country": "Canadá",
      "lat": 75.383, "lon": -89.667, "approximate_coords": false, "description": "...", "clipping": "...",
      "data_notes": null, "listed_as": ["marte"], "batch": "Base v1.1",
      "model_indicates": "marte", "matches_listing": true,
      "image": { "src": "images/analogs/haughton.jpg", "alt": "Encosta coberta de fragmentos...",
                 "caption": "Borda da cratera de impacto de Haughton, ilha Devon", "kind": "foto",
                 "credit": { "author": "Haughton-Mars Project", "license": "Domínio público",
                             "license_url": null, "source_url": "https://commons.wikimedia.org/wiki/File:..." } } }
  ],
  "links": [
    {
      "analog": "haughton", "target": "marte",
      "score": 0.5128, "adherence": 1.5385, "rank": 1, "rank_tied": false, "listed_as_target": true,
      "dimensions": { "ciencia": { "score": 0.8, "adherence": 2.4, "evaluated": 5, "total": 5 } },
      "utilities": [
        { "id": "U06", "name": "Prospecção de gelo", "category": "recursos", "adherence": 2, "score": 0.6667,
          "status": "avaliada", "variables_evaluated": 2, "variables_total": 2, "best_in_network": true,
          "reading": "Permafrost contínuo e polígonos...", "level": "high",
          "meaning": { "purpose": "Prospectar gelo no subsolo (radar, nêutrons)", "condition": "gelo raso em altas latitudes",
                       "criterion": "Gelo em profundidade conhecida, para calibrar instrumentos" },
          "evidence": [{ "variable": "Gelo no subsolo (0–3)", "unit": "escala 0–3", "value": 3, "value_note": null,
                         "note": 3, "level": "high", "status": "avaliada", "direction": "maior",
                         "thresholds": { "3": 3, "2": 2, "1": 1 }, "target_value": "Gelo raso em altas latitudes",
                         "observation": null, "sources": ["F10", "F2"], "sources_scope": "catalogo",
                         "dataset_earth": "SMAP, mapas de permafrost", "dataset_target": "Odyssey GRS, SHARAD" }] }
      ],
      "level": "moderate",
      "strengths": [{ "kind": "reading", "label": "Parecido em", "text": "..." },
                    { "kind": "utility", "id": "U10", "name": "Operações humanas e EVA", "category": "operacoes-humanas",
                      "adherence": 3, "level": "high" }],
      "limits": [{ "kind": "utility", "id": "U15", "name": "Proteção contra radiação", "category": "limitacoes-universais",
                   "adherence": 0, "level": "low" }],
      "to_measure": ["Ciclagem térmica", "Mobilidade em encostas"],
      "best_in_network_count": 6,
      "exploration_use": "...",
      "sources": [{ "id": "F2", "label": "Lee & Osinski 2005, ...", "url": "https://...", "kind": "peer_reviewed" }]
    }
  ],
  "network": {
    "coverage": [{ "target": "marte", "evaluated": 15, "covered": 13, "gaps": 2, "to_measure": 2 }],
    "best_by_utility": [{ "utility": "U01", "name": "Frio extremo", "target": "lua", "best_score": 0.5,
                          "best": ["mcmurdo"], "status": "Lacuna" }],
    "conclusions": ["..."], "caveats": ["..."]
  }
}
```

Regras:

- `lat` em graus, de -90 a 90. `lon` em graus, de -180 a 180, positivo para leste, no sistema de coordenadas
  planetocêntrico de cada corpo.
- `adherence` vai de 0 a 3 (escala das planilhas). `score` = `adherence ÷ 3`, de 0 a 1, para largura e cor
  dos arcos. A aderência do link é a média das notas de utilidade do alvo **sem** a categoria
  "Limitações universais" (ela aparece em `dimensions`, mas com `in_score: false`).
- Utilidade sem nota tem `adherence: null` e `status: "a_medir"`; mostre "a medir", nunca zero.
  Categoria sem nenhuma utilidade avaliada fica fora do objeto `dimensions`. Nunca invente valor.
- Todo análogo tem um link para cada alvo (Lua e Marte). `rank` é a posição do análogo entre os 14 para
  aquele alvo. É uma posição única: aderências iguais são desempatadas pela ordem da rede, e `rank_tied`
  é `true` em todo link que divide a aderência com outro local do mesmo alvo (o front mostra a marca de
  empate a partir desse campo, sem comparar notas).
- `level` (no link, em `dimensions`, em `utilities` e em cada `evidence`) é o patamar da nota, calculado no
  ETL (`etl/config.py` › `nivel`) com os mesmos limiares dos pontos fortes e fracos: `high` ≥ 2,
  `low` ≤ 1, `moderate` entre os dois e `null` a medir. O front só pinta (verde, âmbar, coral, cinza).
- `strengths` e `limits` são listas de objetos: `kind: "utility"` aponta para uma utilidade do link (`id`),
  onde estão o significado (`meaning`: para que serve, condição no alvo, critério) e a evidência
  (`evidence`: uma linha por variável, com valor no local, nota, faixas, valor no alvo, observação do
  local, ids das fontes e dataset de referência); `kind: "reading"` é a leitura qualitativa da base
  ("Parecido em" / "Diferente em").
  `strengths` = utilidades com nota ≥ 2 (e, nos 3 locais da base, o "é similar em" da Leitura preliminar).
  `limits` = utilidades com nota ≤ 1 (e o "é diferente em"); é obrigatório e nunca vazio, porque a radiação
  (U15) é uma limitação universal.
- `sources` traz as fontes com link citadas nos dados daquele análogo. É a mesma lista nos dois links do
  análogo e, como as planilhas citam a fonte por variável (não por local), ela é quase a lista inteira do
  lote. Pendência do ETL: separar as fontes gerais do lote das específicas do local.
- Evidência: nos lotes, `sources` são as fontes daquele valor para aquele local (aba Valores,
  `sources_scope: "local"`). Na base, os valores não têm fonte própria e vêm as fontes da variável no
  Catálogo (`sources_scope: "catalogo"`), que valem para os 3 locais da base; o card avisa isso.
  `dataset_earth` / `dataset_target` saem da coluna "Dataset para extrair" do Catálogo: são o dataset de
  referência da variável, não necessariamente a origem do valor. As referências dos ids ficam em
  `source_index` (topo do JSON). `observation` traz só o trecho da observação da planilha que fala do local
  e, quando o valor foi corrigido na curadoria das fontes, o motivo ("Revisão das fontes: …").
- Fontes: só ficam NASA (e portais do desafio: Earthdata, Worldview, PDS, LRO/Diviner; parceiros CSA,
  ESA/Copernicus, JAXA), artigos revisados e órgãos públicos. Wikipedia, imprensa e sites sem revisão são
  descartados no ETL (`etl/config.py` › `FONTES_DESCARTADAS`, ver `etl/SCHEMA.md`) e nunca chegam ao JSON.
  `source_index[id].kind` e `links[].sources[].kind` dizem a classe: `nasa`, `nasa_mission`,
  `peer_reviewed`, `agency` ou `team`; o card mostra a etiqueta (NASA, Missão NASA, Artigo revisado, Órgão
  público, Planilha) e o front não decide a classe.
- `narrative` é o parágrafo de "Por que é análogo" escrito a partir do dossiê
  (`docs/referencia-analogos-pitch.md`) e das planilhas, só com números das planilhas
  (`etl/config.py` › `NARRATIVAS`); `null` nos locais sem texto curado, que usam `description`.
- `image` é a foto do local mostrada no topo do card. Não vem das planilhas: a escolha (arquivo, legenda,
  texto alternativo, autor, licença e link da fonte) fica em `etl/config.py` › `IMAGENS`, e o arquivo em
  `web/images/analogs/<id>.jpg` (máx. 1200 px de largura). `kind` é `foto` (de campo) ou `satelite`.
  `license_url` é `null` em domínio público. O ETL falha se um local não tiver entrada ou arquivo.
  O schema aceita `null`, e o front mostra o card sem foto nesse caso.

## 4. ETL Python

- Python 3.11+. Dependências em `requirements.txt` (`openpyxl`, `jsonschema`, `pytest`). Ambiente:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- **Entrada:** as planilhas da equipe em `data/raw/` (fora do git): `Base_referencia_v1.1.xlsx`,
  `Lote2_7_locais.xlsx`, `Lote3_locais_brasileiros.xlsx` e `Rede_de_analogos.xlsx`.
- Comando único: `python -m etl build` gera `data/processed/` e `web/data/analogs.json`
  (`python -m etl check` só recalcula e valida, sem gravar). Testes: `python -m pytest`.
- **O ETL recalcula, não copia.** As notas são refeitas em Python (`etl/scoring.py`) a partir dos critérios e
  dos valores de entrada, e depois comparadas célula a célula com os valores em cache do Excel
  (tolerância 1e-9). Se houver divergência, o comando sai com código 1 e não grava nada
  (`--allow-divergences` grava mesmo assim). O relatório fica em `data/processed/relatorio_validacao.md`.
- Modelo (fórmulas na docstring de `etl/scoring.py`):
  - nota da variável 0–3 pelas faixas do critério (`maior`/`menor`); vazio = a medir (`null`, nunca 0);
  - nota da utilidade = média das notas de variável não vazias; categoria = média das utilidades;
  - aderência do local ao alvo = média das utilidades do alvo, sem "Limitações universais";
  - rede: melhor local por utilidade, empates, segunda nota e situação (Coberta ≥ 2, Lacuna < 2, A medir).
  - Todos os pesos valem 1; o código já aceita pesos.
- **Conjuntos de critérios:** a base v1.1 e os lotes usam critérios um pouco diferentes (UV em escala 0–3 na
  base, índice UV do NASA POWER nos lotes; radiação em uma ou duas variáveis). Cada planilha aponta para um
  conjunto (`base-v1-1` ou `lotes-v1-1`) em `etl/config.py`; o ETL confere que os lotes 2 e 3 têm critérios
  idênticos.
- Decisões que não vêm das planilhas (aliases dos locais, coordenada aproximada do Vale da Morte,
  unidade da rugosidade, variáveis renomeadas) ficam todas em `etl/config.py`.
- Dicionário de dados de `data/processed/`: `etl/SCHEMA.md` (copiado para a pasta a cada build).
- O JSON do site é validado contra `etl/analogs.schema.json` e os ids das ligações são conferidos antes de
  gravar.

## 5. Front-end 3D (Three.js)

### Carregamento

- Three.js puro via import map, com versão fixa. Não use `three@latest`.

```html
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
} }
</script>
```

- O JSON é lido com `fetch('data/analogs.json')`. Isso não funciona abrindo o arquivo direto (`file://`).
  Para rodar localmente: `cd web && python -m http.server 8000` e abrir `http://localhost:8000`.

### Cena e layout

- Uma `PerspectiveCamera`, `OrbitControls` para zoom e rotação da cena toda, `AmbientLight` fraca e uma
  `DirectionalLight` como sol.
- Terra: raio 1, na origem.
- Lua e Marte: raios menores, deixe configurável. As proporções reais são Lua 0,27 e Marte 0,53 do raio
  da Terra. Na escala real a Lua fica pequena demais para clicar, então comece com Lua 0,4 e Marte 0,55.
- Lua à esquerda e Marte à direita, em `x = ∓2,8` (ajustar para não cortar em telas estreitas).
- Cada globo é um `THREE.Group` contendo a esfera, os marcadores e o anel de destaque. Girar o grupo gira tudo
  junto.
- Esferas: `SphereGeometry(r, 64, 64)` com `MeshStandardMaterial` e textura equiretangular.

### Texturas

- Use mapas equiretangulares (proporção 2:1) de 2k a 4k pixels, em JPG, em `web/textures/`.
- Fontes sugeridas, a confirmar a licença e citar no README: NASA Blue Marble (Terra), mosaico LROC WAC
  ou o CGI Moon Kit do NASA SVS (Lua), mosaico MOLA/Viking (Marte).
- Configure `texture.colorSpace = THREE.SRGBColorSpace`.

### Conversão lat/lon → posição no globo

Com a `SphereGeometry` padrão e uma textura equiretangular de -180° a 180°, a longitude 0 fica no eixo +X:

```js
export function latLonToVector3(lat, lon, radius) {
  const φ = THREE.MathUtils.degToRad(lat);
  const λ = THREE.MathUtils.degToRad(lon);
  return new THREE.Vector3(
     radius * Math.cos(φ) * Math.cos(λ),
     radius * Math.sin(φ),
    -radius * Math.cos(φ) * Math.sin(λ)
  );
}
```

Teste obrigatório: coloque um marcador num ponto fácil de reconhecer em cada textura (ex.: Rio de Janeiro,
cratera Tycho, Olympus Mons) e confirme que ele cai no lugar certo. Se não cair, a textura tem outra origem
de longitude e é preciso girar a esfera, não a fórmula.

### Marcadores

- Alvos (Lua/Marte): esfera pequena ou sprite, cor por corpo.
- Análogos (Terra): outra forma ou cor, para não confundir com alvos.
- Tamanho em unidades da cena proporcional ao raio do globo, para ter o mesmo tamanho visual nos três.
- Use `InstancedMesh` se passar de algumas centenas de pontos.

### Arcos

- Cada link vira um arco entre o ponto na Terra e o ponto no alvo, em coordenadas do mundo
  (`getWorldPosition` dos marcadores).
- **Hoje só o arco do link ativo é desenhado** (análogo selecionado × alvo ativo). A rede inteira (28 arcos)
  é a próxima fase: `createArcLayer().setLinks([...])` em `arcs.js` já recebe uma lista.
- Curva: Bézier cúbica com os pontos de controle afastados da superfície (ao longo da normal de cada
  ponta), para o arco não atravessar os globos. Altura proporcional à distância entre os pontos.
- Espessura: `linewidth` de `LineBasicMaterial` é ignorado no WebGL. Usamos `Line2` + `LineMaterial` dos
  addons (largura em pixels).
- Escala visual: largura de 1 px (score 0) a 6 px (score 1); cor pelo patamar do link (`level`: verde
  forte, âmbar parcial, coral fraca, cinza a medir; `LEVEL_COLORS` em `arcs.js` = tokens `--lv-*` do CSS).
- A legenda (`#legend`) mostra sempre os patamares da escala 0–3 e, com seleção, o que o arco significa e
  a nota do link ativo.
- Os globos giram, então as pontas mudam: as posições são reescritas a cada frame no buffer que já existe,
  sem recriar a geometria.
- Para a rede completa: arcos que saem da face escondida de um globo precisam perder opacidade ou sumir,
  para não cruzarem a esfera. No arco único isso não acontece, porque as duas pontas ficam de frente.
- Rotação automática: não implementada (se entrar, desligada por padrão, com um botão para ligar).

### Estado da seleção e sincronia

`web/src/selection.js` guarda `{ analogId, targetId }` (começa em `{ null, 'marte' }`) e notifica a lista,
o card e a cena. Os três não conversam entre si. Existe **um só alvo ativo**: ele define a ordem da lista,
a aba do card, o arco e o globo do alvo em foco. Lista e card nunca mostram alvos diferentes.

| Ação do usuário | `analogId` | `targetId` |
|---|---|---|
| Clica num item da lista (ou `Enter`) | o item | não muda |
| Clica num análogo no 3D | o marcador | o alvo para o qual o local foi listado (`listed_as`); listado para os dois = não muda |
| Clica num alvo no 3D (Lua/Marte) | não muda | o alvo clicado |
| Troca o seletor da lista ou a aba do card | não muda | o alvo escolhido |
| `Esc`, ✕ ou clique no vazio | `null` | não muda |

O destaque passageiro (mouse sobre um item ou um marcador) vai por um canal separado (`setHover`), para não
redesenhar lista e card.

### Interação e foco

- `Raycaster`: o raio do ponteiro é testado contra uma esfera de toque em volta de cada marcador (maior
  que o marcador, e maior ainda no toque) e contra os globos, que escondem os marcadores da face de trás.
- Hover mostra um tooltip com o nome e destaca o item da lista; passar o mouse num item destaca o marcador.
- Só conta como clique o gesto que andou menos de 5 px; arrastar para girar a cena não limpa a seleção.
- Ao selecionar um local (`web/src/focus.js`):
  - a Terra gira (slerp de quaternion, 600 ms) até o análogo ficar virado para a câmera, com o norte para
    cima; o globo do alvo ativo faz o mesmo com o alvo;
  - a câmera enquadra a Terra e o globo do alvo ativo na área livre da tela (entre a lista e o card; no
    celular, acima da gaveta), usando `camera.setViewOffset` para deslocar o centro. O foco nunca afasta a
    câmera além do enquadramento inicial nem aproxima mais que 88% dessa distância (`FOCUS_MIN_RATIO` em
    `main.js`), para manter os globos e o arco num enquadramento aberto; em telas estreitas a distância
    fica igual e a cena só é recentralizada. O card tem `--card-w: clamp(380px, 38vw, 500px)`;
  - no desktop, a borda direita da lista e a borda esquerda do card podem ser arrastadas (ou ajustadas com
    as setas, com foco na borda; duplo clique volta ao padrão). A largura vira `--list-w` / `--card-w` no
    `:root`, fica salva no navegador e sempre sobram 260 px para a cena. A cada mudança a câmera
    reenquadra a Terra e o alvo na área livre e se afasta o quanto for preciso para eles não saírem de
    vista (o foco não tem mais o limite de "não afastar além do enquadramento inicial");
  - durante a animação da câmera o `OrbitControls` fica desligado e volta para o usuário no fim;
  - os outros marcadores ficam com opacidade 0,15 e um anel de destaque aparece no análogo e no alvo;
  - o card abre.
- Limpar a seleção devolve a câmera ao enquadramento dos três globos (o cálculo de `resize()`).
- Com `prefers-reduced-motion`, tudo salta direto para a posição final.

### Painel lateral: lista de locais (`#site-list`, esquerda)

- No topo, o seletor de alvo `Lua | Marte` (começa em Marte).
- Os 14 análogos, ordenados pelo `rank` do link com o alvo ativo. Cada item mostra a posição, o nome, o
  país, uma mini barra (largura = `score`; o trilho inteiro é a escala 0–3), a aderência com duas casas e um
  selo do patamar (Forte / Parcial / Fraca), tudo na cor do `level`.
- Marcas: "listado" (`listed_as_target`), "≈ aprox." (`approximate_coords`) e "=" na posição quando há empate
  (`rank_tied`).
- Trocar o alvo reordena a lista com uma animação curta, mantém o item selecionado e o rola até ficar
  visível, sem roubar o foco do teclado.
- Teclado: a lista é um `listbox`; setas (e `Home`/`End`) movem o cursor, `Enter` seleciona, `Esc` limpa.
  O item ativo tem `aria-selected`.

### Card de detalhes (`#panel`, direita)

Não é modal: não escurece o fundo nem bloqueia o globo. Fecha com ✕ ou `Esc`. O cabeçalho (nome completo,
país, lote e aviso de coordenada aproximada) e as abas ficam fixos; o corpo rola.

As abas `Lua | Marte` são o mesmo controle do seletor da lista. A aba do alvo em que a equipe listou o
local leva a marca "listado"; se o card estiver no outro alvo, uma linha discreta avisa e oferece a troca.

No topo do card, acima do nome, fica a foto do local (`image`), com a legenda e o crédito ("Foto: autor ·
licença", com links para a licença e para a página da imagem). Ela carrega sob demanda; se faltar ou não
carregar, o card aparece sem ela. Clicar na foto (ou `Enter` com ela em foco) abre a imagem ampliada num modal
(`<dialog>`, `web/src/lightbox.js`), com legenda e crédito; fecha com ✕, `Esc` ou clique fora da imagem, e o
`Esc` nesse caso não fecha o card. No celular a foto fica mais baixa, para sobrar espaço na gaveta.

Conteúdo da aba (link `analog × target`), nesta ordem:

1. **Veredito:** aderência (`X,XX / 3`) na cor do patamar, selo ("Forte analogia", "Analogia parcial",
   "Baixa aderência"), posição (`Nº de 14`, com aviso de empate se `rank_tied`), `best_in_network_count`
   e, para dar escala, a aderência do 1º colocado daquele alvo. O card não confronta o "listado como" da
   equipe com o `model_indicates` (`matches_listing` segue no JSON, mas não é exibido).
2. **Por que é análogo:** `narrative` (ou `description`), a justificativa da planilha, `clipping` e
   `data_notes`.
3. **Pontos fortes da analogia** (`strengths`), em bloco verde: um card por ponto com a nota, o que mede
   (`meaning`), por que essa nota aqui (as variáveis com nota em `evidence`, com valor, faixas, valor no
   alvo e observação) e a fonte (chips com link; dataset de referência em itálico).
4. **Onde a analogia falha** (`limits`), em bloco coral, com o mesmo formato. O bloco fica sempre aberto,
   com o título e a nota de cada falha à vista; só o detalhe de cada ponto recolhe.

   Nos dois blocos cada ponto é um `<details>`: o resumo (nome, finalidade e nota) aparece sempre, o
   detalhe abre no clique, e "Expandir todos / Recolher todos" abre ou fecha o bloco inteiro. O que o
   usuário abriu continua aberto ao trocar de aba ou de local.
5. **Ainda a medir** (`to_measure`).
6. **Desempenho por categoria:** uma barra por `dimensions`, na cor do patamar, com a nota e quantas
   utilidades a sustentam. "Limitações universais" aparece separada, como fora da nota.
7. **Uso na exploração** (`exploration_use`).
8. **Utilidades** (`utilities`), agrupadas por categoria e coloridas pelo patamar: nota ou "a medir", selo
   "melhor da rede" e o texto `reading` quando existir. Começa recolhida.
9. **Fontes dos dados deste local** (`sources`), com links e a etiqueta da classe (`kind`); recolhida, com
   a contagem.

Categoria ausente no JSON e utilidade com `adherence: null` aparecem como "a medir", não como zero.
O front só formata (vírgula decimal, `1º de 14`); nenhum número é recalculado.

### Acessibilidade e desempenho

- A lista de locais é o caminho por teclado para tudo o que o clique no 3D faz.
- Meta de 60 fps num notebook comum. Limite `renderer.setPixelRatio(Math.min(devicePixelRatio, 2))`.
- Celular (largura < 768 px): a lista vira uma folha sobreposta aberta pelo botão "Locais" (fecha ao
  escolher um item) e o card vira uma gaveta embaixo, com ~60% da altura e um botão para expandir. Alvos
  de toque com pelo menos 44 px e sem rolagem horizontal.

## 6. Ordem de implementação

1. Schema do JSON + um `analogs.json` de exemplo feito à mão (desbloqueia o front-end no primeiro dia).
2. Cena com os três globos texturizados e o teste de posição lat/lon.
3. Marcadores a partir do JSON.
4. Arco do link ativo com largura e cor pela nota, mais a legenda.
5. Clique, foco (rotação dos globos e câmera) e destaque.
6. Lista de locais (painel lateral) e card de detalhes.
7. ETL Python gerando o JSON real a partir das planilhas (em paralelo aos passos 2–6).
8. Ajustes de celular e polimento visual.
9. Rede completa: os 28 arcos ao mesmo tempo (pendente).
10. README com como rodar, fontes de dados e créditos das texturas.

## 7. Critérios de pronto

- [ ] `python -m etl build` gera um JSON válido contra o schema, com 0 divergência em relação ao Excel.
- [ ] A página abre com `python -m http.server` sem erros no console.
- [ ] Os pontos de teste caem no lugar certo nos três globos (`?debug=1`).
- [ ] Os 14 locais aparecem na lista (esquerda), ordenados pelo `rank` do alvo ativo.
- [ ] Clicar num item, num marcador ou dar `Enter` gira a Terra e o alvo, desenha o arco do link ativo com
      largura e cor coerentes com a legenda, esmaece o resto, enquadra a câmera e abre o card (direita).
- [ ] Lista e card mostram sempre o mesmo alvo; o clique no 3D segue a tabela de sincronia da seção 5.
- [ ] O card mostra as categorias, as utilidades, os pontos fortes, os limites (sempre visíveis) e as
      fontes; "a medir" nunca aparece como 0 e nenhum número é calculado no front.
- [ ] `Esc`, ✕ e clique no vazio limpam a seleção e devolvem a câmera ao enquadramento inicial.
- [ ] Toda a interação funciona também pela lista de locais, pelo teclado.
- [ ] Funciona a 375 px de largura (lista recolhida, card em gaveta, sem rolagem horizontal).
- [ ] *Pendente (próxima fase):* todo link do JSON aparece como arco (rede de 28 arcos).
- [ ] README cita todos os datasets e texturas usados.
- [ ] O deploy na Vercel abre sem erros no console e mostra o mesmo que a versão local.
