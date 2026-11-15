# LACITE - Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars — NASA Space Apps 2026

Visualizador 3D (Three.js) de locais na Terra análogos aos locais candidatos a base na Lua e em Marte,
com o que cada analogia tem de parecido e onde ela falha.

Instruções completas de desenvolvimento: [`docs/instrucoes-desenvolvimento.md`](docs/instrucoes-desenvolvimento.md).

## Rodar localmente

```bash
cd web && python3 -m http.server 8000
# abra http://localhost:8000  (ou http://localhost:8000/?debug=1 para os pontos de teste de posição)
```

Abrir o `index.html` direto (`file://`) não funciona, porque o JSON é carregado com `fetch`.

## Gerar os dados

Os dados vêm das planilhas do modelo de aderência (base v1.1, lotes 2 e 3 e a rede de análogos). Copie-as para
`data/raw/` (a pasta não vai para o git) e rode:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m etl build   # grava data/processed/ (JSON + CSV + relatório) e web/data/analogs.json
.venv/bin/python -m etl check   # só recalcula e confere com o Excel, sem gravar
.venv/bin/python -m pytest      # testes
```

O ETL recalcula todas as notas em Python e compara, célula a célula, com os valores salvos no Excel.
O resultado da comparação fica em `data/processed/relatorio_validacao.md`; o dicionário de dados, em
[`etl/SCHEMA.md`](etl/SCHEMA.md).

## Deploy de testes na Vercel

O site é estático: a Vercel só publica a pasta `web/`, sem build (configurado em `vercel.json`).
O `web/data/analogs.json` é gerado localmente e **precisa estar commitado** para aparecer no deploy.

**Pela integração com o GitHub (recomendado):**

1. Em vercel.com → *Add New… → Project*, importe o repositório.
2. Deixe *Framework Preset* em **Other** e *Root Directory* na raiz; o resto vem do `vercel.json`.
3. Cada push na `main` atualiza a produção, e cada branch ou PR ganha uma URL de preview própria para testes.

**Pela CLI:**

```bash
npx vercel          # primeira vez: login e vínculo com o projeto; gera uma URL de preview
npx vercel --prod   # publica em produção
```

## Créditos

Texturas: ver [`web/textures/CREDITS.md`](web/textures/CREDITS.md). Fotos dos locais: ver
[`web/images/analogs/CREDITS.md`](web/images/analogs/CREDITS.md). Fontes dos dados: abas Fontes das planilhas
(`data/processed/fontes.json`), citadas em `sources` de cada ligação do `analogs.json`.
