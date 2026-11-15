"""CLI do ETL.

    python -m etl build            # lê data/raw, recalcula, valida contra o Excel e grava tudo
    python -m etl check            # só recalcula e valida (não grava nada)
    python -m etl build --allow-divergences   # grava mesmo com divergências (o relatório lista quais)

Sai com código 1 se houver divergência entre o recalculado e o cache do Excel, ou erro nas planilhas.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config, curadoria, extract, load, scoring, site, transform, validate


def run(raw_dir, out_dir, site_path, write, allow_divergences):
    books, arquivos = extract.load(raw_dir)
    model = transform.build(books, arquivos)
    res = scoring.compute(model)
    val = validate.run(books, model, res)  # confere as planilhas como estão, antes da curadoria
    cur = curadoria.aplicar(model)          # troca fontes descartadas e corrige valores (etl/config.py)
    res_planilha, res = res, scoring.compute(model)
    cur["notas_alteradas"] = curadoria.notas_alteradas(res_planilha, res)
    model["_curadoria"] = cur
    gerado_em = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    site_json = site.build(model, res, gerado_em)
    load.validar_site(site_json)

    print(f"Planilhas: {', '.join(a['arquivo'] for a in arquivos)}")
    print(f"{len(model['locais'])} locais · {len(model['alvos'])} alvos · {len(model['utilidades'])} utilidades · "
          f"{len(model['criterios'])} critérios em {len(model['conjuntos'])} conjuntos · {len(model['valores'])} valores")
    print(f"Recalculado × Excel: {val['comparadas']} células, {val['divergencias']} divergência(s)")
    for d in val["lista_divergencias"][:10]:
        print(f"  ✗ {d['aba']} | {d['chave']} | {d['campo']}: Excel={d['excel']!r} recalculado={d['recalculado']!r}")
    print(f"Curadoria das fontes: {len(cur['descartadas'])} descartadas, "
          f"{len(cur['valores_corrigidos'])} valores corrigidos, {len(cur['notas_alteradas'])} notas recalculadas")
    for a in model["avisos"]:
        print(f"  aviso: {a}")
    aprox = [l["nome"] for l in model["locais"] if l["coordenada_aproximada"]]
    if aprox:
        print(f"  coordenadas aproximadas: {', '.join(aprox)}")

    if val["divergencias"] and not allow_divergences:
        print("Nada foi gravado. Corrija as planilhas/regras ou use --allow-divergences.", file=sys.stderr)
        return 1
    if write:
        arquivos_out = load.write_all(model, res, val, site_json, gerado_em, out_dir, site_path)
        print(f"Gravados {len(arquivos_out)} arquivos em {out_dir} e o JSON do site em {site_path}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m etl", description="ETL das planilhas de análogos Terra × Lua × Marte")
    p.add_argument("comando", choices=["build", "check"])
    p.add_argument("--raw", type=Path, default=config.RAW_DIR, help="pasta com as planilhas (padrão: data/raw)")
    p.add_argument("--out", type=Path, default=config.PROCESSED_DIR, help="pasta de saída (padrão: data/processed)")
    p.add_argument("--site", type=Path, default=config.SITE_JSON, help="JSON do site (padrão: web/data/analogs.json)")
    p.add_argument("--allow-divergences", action="store_true")
    a = p.parse_args(argv)
    try:
        return run(a.raw, a.out, a.site, a.comando == "build", a.allow_divergences)
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
