# LACITE - Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars — Space Apps 2026

Visualizador 3D (Three.js) de análogos terrestres para locais candidatos na Lua e em Marte,
alimentado por um JSON gerado por um ETL Python a partir das planilhas da equipe.

Antes de implementar qualquer coisa, leia `docs/instrucoes-desenvolvimento.md`: arquitetura,
contrato do `analogs.json`, regras do front-end e critérios de pronto.

- Rodar o front-end: `cd web && python -m http.server 8000`
- Gerar os dados: `.venv/bin/python -m etl build` (lê `data/raw/*.xlsx`, grava `data/processed/` e `web/data/analogs.json`; `check` só valida)
- Testes: `.venv/bin/python -m pytest`
- Deploy de testes: Vercel estática, publica só `web/` (`vercel.json`); o `analogs.json` precisa estar commitado.
- O front-end não calcula semelhanças; todo número vem do JSON.
- O ETL recalcula as notas e compara com o cache do Excel; divergência = erro (não grava nada).
- Decisões de modelagem (aliases, conjuntos de critérios, overrides) ficam em `etl/config.py`.
- Mudanças no formato do JSON exigem atualizar `etl/analogs.schema.json`, `etl/SCHEMA.md` e o documento de instruções.
