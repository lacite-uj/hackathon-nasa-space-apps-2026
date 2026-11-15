# Dicionário de dados — `data/processed/`

Gerado por `python -m etl build` a partir das planilhas em `data/raw/`. Este arquivo é copiado de
`etl/SCHEMA.md` a cada build (a pasta `data/processed/` não vai para o git).

## Convenções

- **Formato longo**: uma linha por fato (ex.: local × variável). Os arquivos não mudam de forma quando
  entra um local novo.
- **Ids estáveis** em slug: `local_id` (`vale-da-morte`), `alvo_id` (`lua`, `marte`), `categoria_id`
  (`pouso-e-mobilidade`), `variavel_id` (`temperatura-media`), `conjunto_id` (`base-v1-1`, `lotes-v1-1`).
  Utilidades mantêm o código da planilha (`U01`–`U19`). Fontes mantêm o código com prefixo por planilha
  (`F`, `G`, `H`, `R`); `N` são as fontes acrescentadas na curadoria (`etl/config.py` › `FONTES_NOVAS`).
- **`null` = ausente / a medir**. Nunca é zero e não entra em média.
- Números são números (ponto decimal no JSON e no CSV). Textos em português ficam como na planilha.
- Escala das notas: **0 a 3** (0 = não serve, 3 = forte).
- Cada arquivo `X.json` tem um `csv/X.csv` equivalente (UTF-8, vírgula, ponto decimal). No CSV, objetos
  viram colunas `campo_subcampo`, listas simples viram `a; b` e listas de objetos viram JSON.
- `analogos.bundle.json` = todos os arquivos abaixo + `metadata`, num só arquivo.

## Arquivos de cadastro

### `locais.json` — os 14 locais na Terra
| Campo | Tipo | Exemplo / descrição |
|---|---|---|
| `id` | string | `vargeao` |
| `nome` | string | Nome curto (aba Locais da rede): `Vargeão` |
| `nome_completo` | string | Nome na aba Locais da planilha de origem: `McMurdo Dry Valleys` |
| `aliases` | string[] | Todos os nomes com que aparece nas abas |
| `pais` | string | `Brasil` |
| `lote` | string | Planilha de origem: `base-v1-1`, `lote-2`, `lote-3` |
| `conjunto_criterios` | string | `base-v1-1` ou `lotes-v1-1` |
| `listado_como` | string[] | De que alvo é considerado análogo: `["lua", "marte"]` |
| `lat`, `lon` | number | Graus; lon de −180 a 180, positivo para leste |
| `coordenada_aproximada` | boolean | `true` no Vale da Morte (célula da fonte F33) e no Cinder Lake (planilha diz "aproximada") |
| `coordenada_obs` | string \| null | Por que a coordenada é aproximada |
| `recorte` | string \| null | Recorte geográfico usado |
| `por_que_recorte` | string \| null | Só na base |
| `justificativa` | string \| null | "Por que é análogo" (só nos lotes) |
| `obs_dados` | string \| null | Observação sobre os dados (ex.: pixel do NASA POWER) |
| `fonte_ids` | string[] | Fontes citadas na justificativa |
| `leitura_qualitativa` | object[] | Só base: `{alvo_id, grau_hipotese, similar_em, diferente_em, utilidade}` |

### `alvos.json` — Lua (Shackleton) e Marte (Jezero)
`id`, `nome`, `corpo` (`moon` / `mars`), `local_referencia`, `lat`, `lon`, `recorte`, `por_que_recorte`.

### `utilidades.json` — U01–U19
`id`, `nome`, `nome_curto` (da Matriz por Utilidade), `aliases` (nomes abreviados usados nos lotes),
`categoria_id`, `alvos` (`["lua","marte"]`), `condicao`, `variaveis_decisivas`, `criterio_aderencia`.

### `categorias.json`
`id`, `nome`, `entra_na_aderencia` (`false` só em `limitacoes-universais`), `utilidade_ids`,
`n_utilidades_por_alvo` (`{"lua": 5, "marte": 4}`).

### `variaveis.json` — variáveis de pontuação (canônicas)
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | string | `dose-radiacao-pct-lua` |
| `nome` | string | Nome canônico (o da aba Valores dos lotes, quando existe) |
| `aliases` | string[] | Todos os nomes vistos (ex.: `Dose de radiação como % da do alvo`) |
| `unidade` | string \| null | `°C`, `escala 0–3`, `m`... |
| `tipo` | string | `numerico` ou `escala_0_3` |
| `conjuntos` | string[] | Conjuntos de critérios que usam a variável |
| `observacao` | string \| null | Ex.: rugosidade em `m` (a base dizia `índice`) |

Decisões: a "Dose de radiação como % da do alvo" da base vira duas variáveis
(`dose-radiacao-pct-lua`, `dose-radiacao-pct-marte`), as mesmas dos lotes. O UV **não** é unificado:
`nivel-de-uv-0-3` (base, escala da literatura) e `indice-uv-medio-anual` (lotes, NASA POWER) são variáveis
diferentes, cada uma com seus critérios.

### `conjuntos_criterios.json`
`id`, `planilha_origem`, `planilhas` (que planilhas usam o conjunto), `n_criterios`.

### `criterios.json` — utilidade × alvo × variável, por conjunto (2 × 48)
| Campo | Tipo | Exemplo |
|---|---|---|
| `id` | string | `base-v1-1.U01.lua.temperatura-media` |
| `conjunto_id`, `utilidade_id`, `alvo_id`, `variavel_id` | string | chaves |
| `variavel_nome`, `unidade` | string | como na planilha |
| `valor_no_alvo` | string \| null | Texto: `≈−236 (PSR, 37 K)` |
| `sentido` | string | `maior` ou `menor` |
| `faixas` | object | `{"nota_3": -150, "nota_2": -80, "nota_1": -20}`; `null` = sem faixa (a medir) |
| `justificativa` | string \| null | "Por que essas faixas" |
| `peso` | number | Sempre 1 por enquanto |
| `planilha_origem`, `linha_excel` | | Rastreabilidade |

### `valores.json` — local × variável (entrada do modelo)
| Campo | Tipo | Exemplo |
|---|---|---|
| `local_id`, `variavel_id` | string | chaves |
| `valor` | number \| null | `13.8`; `null` = a medir |
| `status` | string | `com_valor` ou `a_medir` |
| `status_texto` | string \| null | Texto original da ausência: `A extrair (MODIS)` |
| `fonte_ids` | string[] | Fontes que valem para ESTE local: `G1; McMurdo: G12` dá `["G12"]` para McMurdo e `["G1"]` para os outros |
| `fonte_texto` | string \| null | Célula de fonte original |
| `observacao` | string \| null | Observação da linha (ex.: correção de altitude do Mauna Kea) |
| `origem` | string | Célula de origem: `Lote2_7_locais.xlsx › Valores!C13` |

Na base, os valores são digitados direto na aba Critérios e não têm coluna de fonte; as fontes por
variável estão em `catalogo_referencia.json`.

### `catalogo_referencia.json` — aba Catálogo da base (descritivo)
Uma linha por variável descritiva × entidade (3 locais da base + Lua + Marte):
`variavel_id`, `dimensao`, `variavel`, `unidade`, `entidade_id`, `entidade_tipo` (`local`/`alvo`),
`valor_texto` (original), `valor_num` ou `valor_min`/`valor_max` (faixa), `qualificador` (`≈`, `<`, `>`...),
`a_medir`, `status`, `dataset`, `fonte_ids`, `fonte_texto`, `origem`.
O parser só extrai número quando o texto começa com ele (ex.: `≈900 (alt. ~1.000 m)` → 900;
`−5,7 a 37,9` → faixa). Textos como `≈38 (Badwater) a 42 (Furnace Creek)` ficam só como texto.

### `fontes.json`
`id`, `planilha_id`, `planilha`, `referencia`, `fornece`, `link`, `observacao`.

### `textos.json`
`planilha_id`, `aba`, `bloco` (`introducao`, `cuidados-ao-ler`, `leitura-dos-resultados`,
`conclusao-apollo-artemis`, `como-o-coeficiente-e-calculado`, `historico-de-mudancas`), `titulo`, `linhas`.

## Resultados do modelo (recalculados em Python)

### `notas_variavel.json` — local × critério
`local_id`, `criterio_id`, `conjunto_id`, `utilidade_id`, `alvo_id`, `variavel_id`, `valor`, `nota` (0–3 ou
`null`), `status` (`avaliada`, `a_medir`, `sem_faixas`).

### `notas_utilidade.json` — local × utilidade × alvo
`local_id`, `utilidade_id`, `alvo_id`, `categoria_id`, `nota` (média das notas de variável não nulas),
`status` (`avaliada`/`a_medir`), `n_variaveis`, `n_variaveis_avaliadas`, `leitura` (texto da Matriz da base;
só nos 3 locais da base).

### `notas_categoria.json` — local × categoria × alvo
`local_id`, `categoria_id`, `alvo_id`, `nota`, `n_utilidades`, `n_avaliadas_local`, `n_avaliadas_rede`
(quantas utilidades da categoria têm nota em algum dos 14 locais).

### `aderencia.json` — local × alvo
| Campo | Descrição |
|---|---|
| `aderencia` | Média das notas de utilidade do alvo, **sem** `limitacoes-universais` |
| `n_utilidades`, `n_consideradas` | Total de utilidades do alvo e quantas entraram na média |
| `n_fortes` | Utilidades com nota 3 |
| `n_a_medir` | Utilidades sem nota |
| `n_melhor_em` | Utilidades do alvo em que o local é (ou empata como) o melhor da rede, com nota ≥ 2 |
| `modelo_indica` | `lua`, `marte` ou `empate` (compara as duas aderências do local) |
| `bate` | `modelo_indica` está em `listado_como`? |
| `rank` | Posição do local entre os 14 para este alvo (1 = maior aderência). Posição única: empates são desempatados pela ordem da rede |
| `rank_empatado` | `true` se outro local tem a mesma aderência para este alvo (tolerância `TOLERANCIA_EMPATE` em `etl/config.py`). No `analogs.json` vira `links[].rank_tied` |

### `melhor_por_utilidade.json` — utilidade × alvo (rede)
`utilidade_id`, `alvo_id`, `categoria_id`, `melhor_nota`, `melhor_local_id` (primeiro na ordem da rede),
`empatados`, `n_empatados`, `segunda_nota`, `segundo_local_id`, `situacao` (`Coberta` se melhor ≥ 2,
`Lacuna` se < 2, `A medir` se ninguém tem nota).

### `cobertura.json` — por alvo
`alvo_id`, `total`, `avaliadas`, `cobertas`, `lacunas`, `a_medir`.

### `validacao.json` — casos da literatura (aba Validação da base)
`id`, `local_id`, `alvos`, `utilidade_id` (`null` no caso agregado), `descricao`, `literatura`, `fonte_ids`,
`expectativa`, `regra` (`nota >= 2`, `nota <= 1` ou `aderencia_marte - aderencia_lua > 0`), `nota_modelo`, `bate`.

## Metadados e relatórios

- `metadata.json`: `modelo`, `data_planilhas`, `versao_etl`, `gerado_em`, `escala`, `avisos` e
  `arquivos_origem` (`arquivo`, `sha256`, `abas`) — o hash diz exatamente de qual versão das planilhas
  os dados saíram.
- `relatorio_validacao.json`: cada célula do Excel comparada com o recalculado (`comparadas`,
  `divergencias`, `por_aba`, `lista_divergencias`), tolerância 1e-9.
- `relatorio_validacao.md`: o mesmo em texto, mais o resumo do que ficou `null` e a curadoria das fontes.
- `curadoria_fontes.json`: fontes por classe, fontes descartadas (motivo e substitutas), valores corrigidos
  (valor da planilha → valor novo, com o motivo) e notas que mudaram em relação à planilha.

## Curadoria das fontes

A conferência com o Excel (acima) usa as planilhas como estão. Depois dela, `etl/curadoria.py` aplica as
regras de `etl/config.py`:

- `FONTES_CLASSE`: classe de cada fonte mantida — `nasa` (documento, dado ou página oficial da NASA ou dos
  portais do desafio), `nasa_mission` (artigo revisado com dados de missão da NASA), `peer_reviewed`,
  `agency` (órgão público ou repositório científico) e `team` (planilhas). Fonte sem classe = erro.
- `FONTES_DESCARTADAS`: Wikipedia, imprensa, enciclopédia, blog e site sem revisão, com o motivo e as
  substitutas. A substituta precisa confirmar o mesmo dado; se a fonte oficial der outro número, a lista
  fica vazia e o valor vai para `VALORES_CORRIGIDOS`. Os ids descartados são trocados em `fonte_ids` e nos
  textos (`(H10, H11)` → `(H11, N14)`); `fontes.json` guarda a fonte descartada com `classe: "descartada"`,
  `descarte` e `substituida_por`, mas ela nunca vai para o site.
- `FONTES_NOVAS` e `FONTES_LINK`: fontes novas (`N…`) e notícias trocadas pelo artigo original.
- `VALORES_CORRIGIDOS`: valores que perderam a fonte; `valores.json` ganha `correcao` (o motivo). Erro se
  um valor com dado ficar sem nenhuma fonte válida.
- `OBSERVACOES_CORRIGIDAS` e `DATASETS_REMOVIDOS`: trechos de observação que citavam dado descartado e
  datasets fora dos portais (ERA5, CHIRPS, Mars Climate Database).

As notas são recalculadas depois da curadoria; as do site são essas.

## Site (`web/data/analogs.json`)

Gerado junto, com o contrato descrito em `docs/instrucoes-desenvolvimento.md` (seção 3) e validado contra
`etl/analogs.schema.json`. Usa os mesmos ids (`analogs[].id` = `local_id`, `targets[].id` = `alvo_id`).
`analogs[].image` (foto e crédito de cada local) não vem das planilhas: vem de `etl/config.py` › `IMAGENS`
e dos arquivos em `web/images/analogs/`.
Também não vêm das planilhas: `analogs[].narrative` (`NARRATIVAS`) e o mapeamento variável de pontuação →
variável do Catálogo (`VARIAVEL_CATALOGO`), usado para achar as fontes e o dataset de cada evidência na base.
`source_index[id].kind` e `links[].sources[].kind` são a classe da fonte (`FONTES_CLASSE`).
