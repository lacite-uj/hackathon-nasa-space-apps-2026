# Relatório do ETL — Base de referência v1.1 – 14/11/2026

Gerado em 2026-11-15T17:32:16Z a partir das planilhas de 2026-11-14.

## Recalculado × Excel

Comparadas **2681** células com tolerância 1e-09: **0 divergência(s)**.

| Planilha › aba | Comparadas | Divergências |
|---|---:|---:|
| Base_referencia_v1.1.xlsx › Critérios | 144 | 0 |
| Lote2_7_locais.xlsx › Critérios | 672 | 0 |
| Lote3_locais_brasileiros.xlsx › Critérios | 384 | 0 |
| Base_referencia_v1.1.xlsx › Matriz por Utilidade | 96 | 0 |
| Base_referencia_v1.1.xlsx › Matriz por Categoria | 60 | 0 |
| Lote2_7_locais.xlsx › Matriz por Utilidade | 224 | 0 |
| Lote2_7_locais.xlsx › Matriz por Categoria | 96 | 0 |
| Lote3_locais_brasileiros.xlsx › Matriz por Utilidade | 128 | 0 |
| Lote3_locais_brasileiros.xlsx › Matriz por Categoria | 60 | 0 |
| Base_referencia_v1.1.xlsx › Resumo | 18 | 0 |
| Lote2_7_locais.xlsx › Resumo | 28 | 0 |
| Lote3_locais_brasileiros.xlsx › Resumo | 16 | 0 |
| Rede_de_analogos.xlsx › Notas | 448 | 0 |
| Rede_de_analogos.xlsx › Melhor por utilidade | 224 | 0 |
| Rede_de_analogos.xlsx › Por local | 56 | 0 |
| Rede_de_analogos.xlsx › Resumo | 8 | 0 |
| Base_referencia_v1.1.xlsx › Validação | 19 | 0 |

## Aderência por local (0–3, sem limitações universais)

| Local | Lua | Marte | O modelo indica | Bate com 'listado como'? | Melhor em (nota ≥ 2) |
|---|---:|---:|---|---|---:|
| Atacama | 0.4091 | 0.9643 | marte | sim | 4 |
| Haughton | 1.1818 | 1.5385 | marte | sim | 8 |
| Vale da Morte | 0.9091 | 1.1250 | marte | sim | 4 |
| Cinder Lake | 0.6250 | 0.7143 | marte | não | 1 |
| Meteor Crater | 0.6250 | 0.8214 | marte | não | 3 |
| Holuhraun | 0.6250 | 0.8571 | marte | não | 3 |
| Mauna Kea | 0.5000 | 0.8214 | marte | não | 1 |
| McMurdo | 0.7917 | 1.0714 | marte | sim | 6 |
| Rio Tinto | 0.3333 | 0.8214 | marte | sim | 2 |
| Askja | 0.5833 | 0.8571 | marte | sim | 1 |
| Vargeão | 0.6250 | 0.9643 | marte | sim | 3 |
| Araguainha | 0.7917 | 1.0357 | marte | sim | 6 |
| Lençóis Maranhenses | 0.2917 | 0.5357 | marte | sim | 2 |
| Toca da Boa Vista | 0.6250 | 0.7143 | marte | sim | 5 |

Cobertura da rede: **lua** 13 avaliadas, 8 cobertas, 5 lacunas, 2 a medir · **marte** 15 avaliadas, 13 cobertas, 2 lacunas, 2 a medir

Validação com a literatura (base): 9 de 9 casos batem.

## O que ficou `null` (a medir)

Utilidades sem nota em nenhum local: U03 (lua), U03 (marte), U09 (lua), U09 (marte).
Variáveis de pontuação sem valor em nenhum local: `amplitude-termica-diaria-do-solo`, `declividade-maxima`, `declividade-media`, `rugosidade-do-terreno`, `teor-de-gelo-no-solo`.

Notas de utilidade calculadas com só parte das variáveis (as demais estão a medir):

- U07 lua: Atacama (2/3), Haughton (2/3), Vale da Morte (2/3), Cinder Lake (2/3), Meteor Crater (2/3), Holuhraun (2/3), Mauna Kea (2/3), McMurdo (2/3), Rio Tinto (2/3), Askja (2/3), Vargeão (2/3), Araguainha (2/3), Lençóis Maranhenses (2/3), Toca da Boa Vista (2/3)
- U07 marte: Atacama (2/3), Haughton (2/3), Vale da Morte (2/3), Cinder Lake (2/3), Meteor Crater (2/3), Holuhraun (2/3), Mauna Kea (2/3), McMurdo (2/3), Rio Tinto (2/3), Askja (2/3), Vargeão (2/3), Araguainha (2/3), Lençóis Maranhenses (2/3), Toca da Boa Vista (2/3)
- U08 lua: Atacama (1/2), Haughton (1/2), Vale da Morte (1/2), Cinder Lake (1/2), Meteor Crater (1/2), Holuhraun (1/2), Mauna Kea (1/2), McMurdo (1/2), Rio Tinto (1/2), Askja (1/2), Vargeão (1/2), Araguainha (1/2), Lençóis Maranhenses (1/2), Toca da Boa Vista (1/2)
- U08 marte: Atacama (1/2), Haughton (1/2), Vale da Morte (1/2), Cinder Lake (1/2), Meteor Crater (1/2), Holuhraun (1/2), Mauna Kea (1/2), McMurdo (1/2), Rio Tinto (1/2), Askja (1/2), Vargeão (1/2), Araguainha (1/2), Lençóis Maranhenses (1/2), Toca da Boa Vista (1/2)
- U01 lua: Haughton (1/2)
- U01 marte: Haughton (1/2)
- U05 marte: Haughton (1/2), Vale da Morte (1/2), Cinder Lake (1/2), Meteor Crater (1/2), Holuhraun (1/2), Mauna Kea (1/2), Rio Tinto (1/2), Askja (1/2), Vargeão (1/2), Araguainha (1/2), Lençóis Maranhenses (1/2), Toca da Boa Vista (1/2)
- U19 marte: Araguainha (1/2)

Valores a medir por local (local × variável): Haughton 9, Atacama 6, Vale da Morte 8, Cinder Lake 6, Meteor Crater 6, Holuhraun 6, Mauna Kea 6, McMurdo 5, Rio Tinto 6, Askja 6, Vargeão 6, Araguainha 7, Lençóis Maranhenses 6, Toca da Boa Vista 6.

## Curadoria das fontes (etl/config.py)

A conferência acima usa as planilhas como estão. Depois dela, as fontes sem validação (Wikipedia, imprensa, sites sem revisão) saem e são trocadas por fontes da NASA, artigos revisados ou órgãos públicos; os valores que perderam a fonte são corrigidos e as notas, recalculadas.

Fontes por classe: agency 9, descartada 23, nasa 13, nasa_mission 10, peer_reviewed 23, team 5.

| Fonte descartada | Motivo | Substituída por |
|---|---|---|
| F4 Wikipedia – Haughton impact crater | Wikipedia | N1, F2 |
| F5 Britannica – Death Valley | Enciclopédia (Britannica) | N9 |
| F8 de la Torre Juárez et al. – resumo MEDA | Resumo de congresso, sem revisão | N6 |
| F9 EurekAlert – Univ. do País Basco (MEDA) | Release de imprensa (EurekAlert) | F7 |
| F14 CSEG Recorder – Mars in Canada (HMP) | Revista profissional, sem revisão | F2 |
| F15 Wikipedia – Shackleton (crater) | Wikipedia | N2, N3 |
| F19 PBS Nature – Life in Death Valley | Site de TV (PBS) | — |
| F21 National Parks Traveler | Site de notícias (National Parks Traveler); 'umidade abaixo de 1%' não foi confirmada | — |
| F22 Wikipedia – Death Valley National Park | Wikipedia; os 38 mm de Badwater não foram confirmados (ver VALORES_CORRIGIDOS) | — |
| F23 Phys.org – primeiro boletim de Jezero (MEDA) | Site de notícias (Phys.org) | N4 |
| F24 ScienceDaily – Univ. de Kiel (LND) | Site de notícias (ScienceDaily) | F11 |
| F25 Wikipedia – Jezero (crater) | Wikipedia | F16, N18 |
| F27 EurekAlert – Diviner (LRO) | Release de imprensa (EurekAlert) | N5 |
| F28 Sorbonne (HAL) – perclorato no Ártico marciano | Cópia em arquivo aberto sem referência verificável | N16 |
| F29 Leonard David – regiões candidatas do Artemis III | Blog de jornalista | N7 |
| F31 Space.com – MarsFest em Death Valley | Site de notícias (Space.com) | N8 |
| F33 WorldSpecies – clima da célula 36,25 N, −116,75 | Site agregador sem revisão (WorldSpecies); valor trocado pelo NASA POWER (VALORES_CORRIGIDOS) | — |
| G2 Wikipedia – Apollo program training | Wikipedia | N10 |
| G4 NBC News / Space.com – Meteor Crater | Site de notícias (NBC/Space.com) | N11, N10 |
| G5 Exploration Museum – treino Apollo na Islândia | Site de museu | N10 |
| G12 Wikipedia – McMurdo Dry Valleys | Wikipedia; a média de −19,8 °C não foi confirmada (ver VALORES_CORRIGIDOS) | — |
| H9 Agência FAPESP / phys.org 2020 – dinâmica de dunas barcanas | Site de notícias (FAPESP/Phys.org) | N13 |
| H10 Wikipedia – Toca da Boa Vista | Wikipedia | H11, N14 |

Valores corrigidos:

- vale-da-morte › temperatura-media: 18.5 → 19.2 (N17). o valor de 18,5 °C da planilha vinha de site sem revisão; trocado pelo NASA POWER no mesmo ponto (19,2 °C).
- vale-da-morte › precipitacao-anual: 38.0 → 49.0 (N9). o valor de 38 mm (Badwater) da planilha vinha de fonte não validada; o NPS dá 49 mm/ano em Furnace Creek, a estação oficial do vale.
- mcmurdo › temperatura-media: -19.8 → -14.8 (N12). o valor de −19,8 °C da planilha vinha de fonte não validada. A fonte revisada (Doran et al. 2002) dá médias de −14,8 a −30,0 °C nas estações do fundo dos vales; usado o limite mais quente (conservador: não aumenta nenhuma nota). O pixel do NASA POWER (−27,2 °C) inclui o planalto.

Notas que mudaram em relação à planilha:


## Decisões e observações preservadas

- **Vale da Morte**: coordenada aproximada — Aba Locais da base diz 'a confirmar'; usada a célula 36,25 N, −116,75 da fonte F33.
- **Cinder Lake**: coordenada aproximada — Coordenada aproximada; clima do NASA POWER
- Cinder Lake (dados): Coordenada aproximada; clima do NASA POWER
- Meteor Crater (dados): Clima do NASA POWER
- Holuhraun (dados): Cai no mesmo pixel do POWER que Askja: clima idêntico
- Mauna Kea (dados): Pixel do POWER a 636 m: temperaturas corrigidas para 2.800 m (estimadas)
- McMurdo (dados): Temperatura média e chuva da literatura local; o resto do POWER
- Rio Tinto (dados): Clima do NASA POWER
- Askja (dados): Cai no mesmo pixel do POWER que Holuhraun
- Vargeão (dados): Clima do NASA POWER (pixel ~50 km)
- Araguainha (dados): Clima do NASA POWER; alteração hidrotermal a verificar
- Lençóis Maranhenses (dados): Clima do NASA POWER; chuva alta, ao contrário de Marte
- Toca da Boa Vista (dados): Clima do NASA POWER (superfície, não o interior da caverna)
- Catálogo marca discrepância entre fontes em **Precipitação anual** — Atacama: ≈0,6 (1 chuva de 2,3 mm em 4 anos) | Haughton: <13 ou ≈160 eq. água (as fontes divergem) | Vale da Morte: ≈38 (Badwater) a 42 (Furnace Creek)
- Catálogo marca discrepância entre fontes em **Idade da feição** — Atacama: Deserto hiperárido há muito tempo; sem chuva no núcleo há ~20 mil anos | Haughton: 31–32 (antes: 39 ou 23) | Vale da Morte: Ubehebe: geologicamente recente
- Aviso: Texto de 'Condição que o alvo impõe' nos lotes difere da base (usado o da base): U02 (lote-2 e lote-3), U05 (lote-2 e lote-3), U06 (lote-2 e lote-3), U13 (lote-2 e lote-3), U15 (lote-2 e lote-3), U17 (lote-2 e lote-3), U18 (lote-2 e lote-3), U19 (lote-2 e lote-3)
