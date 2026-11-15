# Prompt para o Claude Code — ETL das planilhas de análogos (Terra × Lua × Marte)

> Cole tudo abaixo no Claude Code, na raiz do repositório. Antes, copie as planilhas para `data/raw/` (veja a seção 2).

---

## 1. Contexto

Estou no NASA Space Apps Challenge 2026, no desafio *"Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars"*. Minha equipe montou em Excel um modelo que dá uma nota de aderência (0–3) a **14 locais da Terra** contra **2 alvos** (Lua – polo sul/Shackleton e Marte – cratera Jezero) em **19 utilidades** de exploração. O front-end vai mostrar um **globo web** com esses locais, as notas e as comparações.

**Objetivo:** criar um pipeline em Python que leia as planilhas, normalize os dados, **recalcule** todas as notas com a mesma lógica das fórmulas do Excel (para não depender de valores em cache), valide o resultado contra o Excel e exporte **JSON e CSV** prontos para o front-end.

Sou estudante de Sistemas de Informação e quero aprender com o processo: explique as decisões de modelagem conforme avança e **me pergunte** quando algo for ambíguo, em vez de supor.

## 2. Arquivos de entrada (`data/raw/`)

| Arquivo | Papel | Usar? |
|---|---|---|
| `Base_referencia_v1.1.xlsx` | Modelo (utilidades, critérios, fórmulas) + 3 locais: Atacama (Yungay), Haughton, Vale da Morte. Fontes F1–F35 | **Sim — fonte principal** |
| `Lote2_7_locais.xlsx` | 7 locais: Cinder Lake, Meteor Crater, Holuhraun, Mauna Kea, McMurdo, Rio Tinto, Askja. Fontes G1–G15 | **Sim** |
| `Lote3_locais_brasileiros.xlsx` | 4 locais: Vargeão, Araguainha, Lençóis Maranhenses, Toca da Boa Vista. Fontes H1–H12 | **Sim** |
| `Rede_de_analogos.xlsx` | Consolidação dos 14 locais (Notas, Melhor por utilidade, Por local, Resumo com conclusões) | **Sim — para validação e textos de conclusão** |
| `Catálogo de variáveis — Análogos Terra × Lua × Marte.xlsx` | Versão v1 da base (15 utilidades) | Não — obsoleta (substituída pela v1.1). Confirme comigo antes de descartar |
| `Análogos – Lote 2 7 novos locais × Lua e Marte.xlsx` | Versão antiga do lote 2 (15 utilidades) | Não — obsoleta (substituída por `Lote2_7_locais.xlsx`). Confirme comigo |
| `Pitch – Análogos Terra × Lua × Marte.docx.pdf` | Pitch do projeto | Só contexto, se ajudar a nomear campos |

## 3. Como as planilhas estão organizadas

**Layout comum a todas as abas:** linhas 1–8 são cabeçalho visual; **linha 9 = descrição**, **linha 10 = data**, **linha 12 = cabeçalho da tabela**, **dados a partir da linha 13**. Algumas abas (Resumo, Validação) têm vários blocos empilhados — leia por blocos, não como uma tabela única.

### Base_referencia_v1.1.xlsx
- **Catálogo**: 19 variáveis descritivas por dimensão (Limites universais, Térmica, Água e gelo, Geologia, Relevo, Radiação e luz, Vento e poeira, Biologia, Exploração). Colunas: Dimensão, Variável, Unidade, Atacama, Haughton, Vale da Morte, Lua – polo sul, Marte – Jezero, Status, Dataset para extrair, Fontes. **Valores são texto livre** (ex.: `≈900 (alt. ~1.000 m)`, `A extrair`, `−5,7 a 37,9`) com vírgula decimal e sinal de menos unicode (`−`).
- **Utilidades**: U01–U19 → ID, Utilidade, Categoria, Alvo (Lua / Marte / Lua e Marte), Condição que o alvo impõe, Variáveis que decidem, Critério de aderência.
- **Critérios**: 48 linhas (utilidade × alvo × variável) → ID, Alvo, Variável, Unidade/escala, Valor no alvo (texto), Sentido (`maior`/`menor`), Nota 3 se, Nota 2 se, Nota 1 se, valores dos 3 locais (**digitados direto em J:L**), notas calculadas (M:O), justificativa das faixas.
- **Matriz por Utilidade** (32 linhas utilidade × alvo; tem nome curto da utilidade e coluna "Leitura" com um texto interpretativo por linha), **Matriz por Categoria**, **Resumo**, **Validação** (9 casos literatura × modelo, 9 de 9 batem), **Leitura preliminar** (similar em / diferente em / utilidade, por local × alvo), **Locais** (recorte, lat/lon dos 3 locais **e dos 2 alvos**), **Fontes**.

### Lote2 e Lote3
- **Locais**: Local, Listado como análogo de, Recorte, Latitude, Longitude, Por que é análogo, Observação sobre os dados.
- **Valores**: uma linha por variável, uma coluna por local, + Fonte e Observação. **Aqui estão os valores numéricos de entrada.**
- **Critérios**: mesmas 48 regras, mas os valores dos locais vêm de `Valores` via `INDEX/MATCH` pelo nome da variável.
- Matriz por Utilidade, Matriz por Categoria, Resumo (com "Cuidados ao ler" e "Leitura dos resultados"), Fontes.

### Rede_de_analogos.xlsx
- **Notas**: 32 linhas × 14 locais (cópia das notas por utilidade).
- **Melhor por utilidade**: melhor nota, melhor local, empatados, nº de empatados, segunda nota, local da segunda nota, situação.
- **Por local**: aderência Lua/Marte, "o modelo indica", nº de utilidades em que é o melhor.
- **Locais** (com **País**), **Resumo** (cobertura da rede + conclusões Apollo × Artemis + cuidados ao ler), **Fontes** (R1–R3 apontando para as 3 planilhas).

## 4. Lógica de cálculo (reproduzir em Python)

1. **Nota da variável (0–3)** — fórmula do Excel:
   ```
   se valor vazio ou faixas vazias → vazio (a medir)
   sentido "maior": valor >= n3 → 3; >= n2 → 2; >= n1 → 1; senão 0
   sentido "menor": valor <= n3 → 3; <= n2 → 2; <= n1 → 1; senão 0
   ```
2. **Nota da utilidade** (local × utilidade × alvo) = média simples das notas de variável **não vazias** daquela utilidade e alvo. Se todas vazias → vazio.
3. **Nota por categoria** (local × categoria × alvo) = média das notas de utilidade não vazias da categoria. Guardar também: nº de utilidades na categoria e nº já avaliadas por algum local.
4. **Aderência do local ao alvo** = média das notas de utilidade não vazias do alvo, **excluindo a categoria "Limitações universais"** (U15, radiação).
5. **Resumo por local**: nº de utilidades com nota 3, nº ainda a medir, "o modelo indica" (Lua se aderência Lua > Marte, Marte se o contrário, senão Empate) e "bate?" (o indicado está contido em "listado como análogo de").
6. **Melhor por utilidade** (rede): melhor nota, todos os locais empatados, segunda nota e seu local; **situação** = `A medir` (nenhuma nota), `Coberta` (melhor ≥ 2) ou `Lacuna` (melhor < 2).
7. **Cobertura da rede** por alvo: avaliadas, cobertas, lacunas, a medir.

Todos os pesos são iguais (o modelo ainda não tem pesos). Deixe o código preparado para pesos futuros, mas sem aplicá-los.

## 5. Pegadinhas que já identifiquei (trate explicitamente)

- **Critérios diferem entre a base e os lotes** em algumas linhas:
  - U04 (UV): a base usa `Nível de UV (0–3)` com faixas 3/2/1; os lotes usam `Índice UV médio anual` (NASA POWER) com faixas **2 / 1,5 / 1**.
  - U15 (radiação): a base usa `Dose de radiação como % da do alvo` (0,5 na Lua, 1 em Marte); os lotes têm duas variáveis, `% da lunar` e `% da marciana`.
  - Rugosidade: unidade `índice` na base e `m` nos lotes.
  - Diferenças só de texto em "Valor no alvo" (ex.: `Meridiani Planum` × `Meridiani`).
  → Proponha um modelo (ex.: `conjunto_criterios` por lote, ou variável canônica + aliases) e **me mostre antes de implementar**.
- **Vazio ≠ zero.** Vazio significa "a medir" e não entra na média. Mapeie para `null`, nunca para 0. Textos como `A extrair`, `A medir`, `A verificar`, `—` também viram `null` (guarde o texto original num campo `status`/`observacao`).
- **U03 (ciclagem térmica) e U09 (mobilidade em encostas)** não têm dados em nenhum local → devem sair como `a_medir`.
- **Vale da Morte sem coordenadas** (aba Locais da base diz "a confirmar"). A fonte F33 usa a célula 36,25 N, −116,75; o critério U14 usa latitude 36. Use 36.25 / −116.75 com uma flag `coordenada_aproximada: true` e me avise.
- **Holuhraun e Askja** caem no mesmo pixel do NASA POWER (clima idêntico); **Mauna Kea** teve temperatura corrigida para 2.800 m (estimada); **McMurdo** usa temperatura e chuva de estação local. Preserve essas observações.
- **Haughton – precipitação**: as fontes divergem (<13 ou ≈160 mm); o modelo usa 13.
- **Araguainha – U19**: nota 3 só pela origem por impacto (alteração hidrotermal a verificar).
- **Números em texto** no Catálogo: vírgula decimal, `−` unicode, `≈`, faixas (`0,64–0,67`). Faça um parser que gere `valor_texto` (original) + `valor_min`/`valor_max`/`valor_num` quando der, sem forçar o que não for numérico.
- Nomes dos locais variam entre abas (`Atacama (Yungay)`, `Atacama – Yungay`, `Atacama`; `Holuhraun (Islândia)`; `Cinder Lake Crater Field`). Crie um **id slug estável** por local (ex.: `atacama`, `vale-da-morte`, `toca-da-boa-vista`) e um mapa de aliases.
- Códigos de fonte têm prefixo por planilha (F, G, H, R) — mantenha como estão; as células de fonte podem citar várias (`F1, F2, F9`) ou texto (`G1; McMurdo: G12`). Extraia a lista de IDs e guarde o texto original.

## 6. Valores esperados (use como teste de regressão)

Aderência média (0–3, sem limitações universais), da aba *Por local* da rede:

| Local | Lua | Marte | Melhor em (nota ≥ 2) |
|---|---|---|---|
| Atacama | 0,4091 | 0,9643 | 4 |
| Haughton | 1,1818 | 1,5385 | 8 |
| Vale da Morte | 0,9091 | 1,1250 | 4 |
| Cinder Lake | 0,6250 | 0,7143 | 1 |
| Meteor Crater | 0,6250 | 0,8214 | 3 |
| Holuhraun | 0,6250 | 0,8571 | 3 |
| Mauna Kea | 0,5000 | 0,8214 | 1 |
| McMurdo | 0,7917 | 1,0714 | 6 |
| Rio Tinto | 0,3333 | 0,8214 | 2 |
| Askja | 0,5833 | 0,8571 | 1 |
| Vargeão | 0,6250 | 0,9643 | 3 |
| Araguainha | 0,7917 | 1,0357 | 6 |
| Lençóis Maranhenses | 0,2917 | 0,5357 | 2 |
| Toca da Boa Vista | 0,6250 | 0,7143 | 5 |

Cobertura da rede: **Lua** 13 avaliadas, 8 cobertas, 5 lacunas, 2 a medir · **Marte** 15 avaliadas, 13 cobertas, 2 lacunas, 2 a medir. Validação da base: 9 de 9 casos batem.

Além desta tabela, compare **célula a célula** tudo o que você recalcular com os valores em cache do Excel (`openpyxl` com `data_only=True`), com tolerância de 1e-9, e gere um relatório das divergências.

## 7. Saída esperada

Proponha a estrutura final e **me mostre o esquema antes de gerar os arquivos**. Minha sugestão de ponto de partida (formato longo/normalizado, bom para filtrar no front):

```
data/processed/
  locais.json            # id, nome, aliases, pais, lote, listado_como[], lat, lon, coordenada_aproximada, recorte, justificativa, obs_dados, leitura_qualitativa (quando houver)
  alvos.json             # lua / marte: nome, local de referência (Shackleton, Jezero), lat, lon, por que este recorte
  utilidades.json        # U01–U19: nome, nome_curto, categoria, alvos[], condicao, variaveis_decisivas, criterio_aderencia
  categorias.json
  variaveis.json         # variáveis de pontuação: id, nome, unidade, tipo (numerico | escala_0_3), aliases
  criterios.json         # utilidade × alvo × variável: valor_no_alvo, sentido, faixas {3,2,1}, justificativa, conjunto (base/lotes)
  valores.json           # local × variável: valor (num|null), status, fonte_ids[], fonte_texto, observacao
  catalogo_referencia.json  # Catálogo descritivo (texto + números parseados), incl. colunas da Lua e de Marte
  notas_variavel.json    # local × critério → nota
  notas_utilidade.json   # local × utilidade × alvo → nota, leitura (texto da Matriz quando existir)
  notas_categoria.json
  aderencia.json         # local × alvo → média, n_fortes, n_a_medir, modelo_indica, bate
  melhor_por_utilidade.json
  cobertura.json
  validacao.json
  fontes.json            # id, referencia, fornece, link, planilha
  textos.json            # conclusões, "cuidados ao ler", "leitura dos resultados" (por planilha)
  analogos.bundle.json   # tudo acima num único arquivo, com metadata (versão, data 14/11/2026, gerado_em, arquivos de origem)
  csv/                   # um CSV por tabela (UTF-8, separador vírgula, ponto decimal)
```

Regras: chaves em `snake_case`, ids estáveis, `null` para ausente, números como número (não string), textos em português preservados como estão. Para o globo, garanta que `locais.json` seja suficiente para plotar os pontos (lat/lon numéricos) e que dê para cruzar com as notas pelo `local_id`.

## 8. Entregáveis técnicos

- `etl/` com módulos separados: leitura (`extract`), normalização (`transform`), cálculo do modelo (`scoring`), exportação (`load`) e um CLI único (`python -m etl build`).
- `tests/` com `pytest`: a regra de nota 0–3 (casos de borda: igual ao limite, vazio, faixas vazias), as médias ignorando vazios, a exclusão de "Limitações universais" e a tabela da seção 6.
- `data/processed/SCHEMA.md` (dicionário de dados: cada arquivo, cada campo, tipo, exemplo) e, se fizer sentido, um JSON Schema ou tipos TypeScript (`types.ts`) para o front.
- `requirements.txt` (openpyxl, pandas, pytest; o que mais for necessário).
- O ETL deve ser re-executável: se eu atualizar uma planilha, rodo de novo e tudo se regenera.

## 9. Como quero que você trabalhe

1. **Primeiro explore**: liste abas, dimensões e cabeçalhos de cada arquivo e confirme o que eu descrevi acima. Aponte qualquer diferença.
2. Me apresente o **modelo de dados** (entidades, chaves, relações) e as decisões sobre as pegadinhas da seção 5. **Espere minha aprovação.**
3. Implemente em etapas pequenas, rodando os testes a cada etapa.
4. No fim, gere o relatório de validação (recalculado × Excel) e um resumo do que ficou `null`/a medir.
5. Ao longo do caminho, explique brevemente o porquê das escolhas (normalização, formato longo × largo, slugs, etc.) — quero aprender, não só receber o resultado.
6. Não altere os arquivos em `data/raw/`.
