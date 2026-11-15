"""Load: grava data/processed/ (JSON + CSV + bundle + relatórios) e o web/data/analogs.json.

Tudo é montado e validado em memória antes de escrever. Se algo falhar, nada é gravado; os arquivos
são escritos em temporários e renomeados, para nunca ficar um JSON pela metade.
"""
import csv
import io
import json
import os
import shutil
import tempfile
from collections import Counter

import jsonschema

from . import config

ETL_VERSION = "1.0"

TABELAS = [  # (arquivo sem extensão, chave no modelo ou no resultado)
    ("locais", "locais"), ("alvos", "alvos"), ("utilidades", "utilidades"), ("categorias", "categorias"),
    ("variaveis", "variaveis"), ("conjuntos_criterios", "conjuntos"), ("criterios", "criterios"),
    ("valores", "valores"), ("catalogo_referencia", "catalogo_referencia"),
    ("notas_variavel", "notas_variavel"), ("notas_utilidade", "notas_utilidade"),
    ("notas_categoria", "notas_categoria"), ("aderencia", "aderencia"),
    ("melhor_por_utilidade", "melhor_por_utilidade"), ("cobertura", "cobertura"),
    ("validacao", "validacao"), ("fontes", "fontes"), ("textos", "textos"),
]


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def _flat(row, prefix=""):
    """Achata um registro para CSV: dict -> colunas 'a_b'; lista simples -> 'x; y'; lista de dicts -> JSON."""
    out = {}
    for k, v in row.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "_"))
        elif isinstance(v, list):
            out[key] = json.dumps(v, ensure_ascii=False) if any(isinstance(x, (dict, list)) for x in v) \
                else "; ".join(str(x) for x in v)
        else:
            out[key] = v
    return out


def to_csv(rows):
    flat = [_flat(r) for r in rows]
    campos = []
    for r in flat:
        campos += [k for k in r if k not in campos]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n")
    w.writeheader()
    for r in flat:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue()


def validar_site(site):
    schema = json.loads(config.SITE_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(site)
    targets = {t["id"] for t in site["targets"]}
    analogs = {a["id"] for a in site["analogs"]}
    dims = {d["id"] for d in site["dimensions"]}
    for l in site["links"]:
        if l["analog"] not in analogs or l["target"] not in targets:
            raise ValueError(f"link com id inexistente: {l['analog']} -> {l['target']}")
        if not set(l["dimensions"]) <= dims:
            raise ValueError(f"link {l['analog']}->{l['target']} com dimensão desconhecida")


def relatorio_md(meta, validacao, model, res):
    L = [f"# Relatório do ETL — {meta['modelo']}", "",
         f"Gerado em {meta['gerado_em']} a partir das planilhas de {meta['data_planilhas']}.", "",
         "## Recalculado × Excel", "",
         f"Comparadas **{validacao['comparadas']}** células com tolerância {validacao['tolerancia']}: "
         f"**{validacao['divergencias']} divergência(s)**.", "",
         "| Planilha › aba | Comparadas | Divergências |", "|---|---:|---:|"]
    for k, v in validacao["por_aba"].items():
        L.append(f"| {k} | {v['comparadas']} | {v['divergencias']} |")
    if validacao["lista_divergencias"]:
        L += ["", "### Divergências", "", "| Aba | Chave | Campo | Excel | Recalculado |", "|---|---|---|---|---|"]
        for d in validacao["lista_divergencias"][:200]:
            L.append(f"| {d['aba']} | {d['chave']} | {d['campo']} | {d['excel']} | {d['recalculado']} |")

    L += ["", "## Aderência por local (0–3, sem limitações universais)", "",
          "| Local | Lua | Marte | O modelo indica | Bate com 'listado como'? | Melhor em (nota ≥ 2) |",
          "|---|---:|---:|---|---|---:|"]
    ad = {(a["local_id"], a["alvo_id"]): a for a in res["aderencia"]}
    for l in model["locais"]:
        lu, ma = ad[(l["id"], "lua")], ad[(l["id"], "marte")]
        L.append(f"| {l['nome']} | {lu['aderencia']:.4f} | {ma['aderencia']:.4f} | {lu['modelo_indica']} | "
                 f"{'sim' if lu['bate'] else 'não'} | {lu['n_melhor_em'] + ma['n_melhor_em']} |")
    L += ["", "Cobertura da rede: " + " · ".join(
        f"**{c['alvo_id']}** {c['avaliadas']} avaliadas, {c['cobertas']} cobertas, {c['lacunas']} lacunas, "
        f"{c['a_medir']} a medir" for c in res["cobertura"]), ""]
    ok = sum(v["bate"] is True for v in res["validacao"])
    L.append(f"Validação com a literatura (base): {ok} de {len(res['validacao'])} casos batem.")

    # O que ficou null / a medir
    L += ["", "## O que ficou `null` (a medir)", ""]
    sem_dado = [m for m in res["melhor_por_utilidade"] if m["situacao"] == "A medir"]
    L.append("Utilidades sem nota em nenhum local: " +
             ", ".join(f"{m['utilidade_id']} ({m['alvo_id']})" for m in sem_dado) + ".")
    vals = Counter(v["variavel_id"] for v in model["valores"] if v["status"] == "com_valor")
    usadas = {c["variavel_id"] for c in model["criterios"]}
    L.append("Variáveis de pontuação sem valor em nenhum local: " +
             ", ".join(f"`{v}`" for v in sorted(usadas - set(vals))) + ".")
    parciais = [n for n in res["notas_utilidade"] if n["nota"] is not None and n["n_variaveis_avaliadas"] < n["n_variaveis"]]
    L += ["", "Notas de utilidade calculadas com só parte das variáveis (as demais estão a medir):", ""]
    nomes = {l["id"]: l["nome"] for l in model["locais"]}
    por_u = {}
    for n in parciais:
        por_u.setdefault((n["utilidade_id"], n["alvo_id"]), []).append(
            f"{nomes[n['local_id']]} ({n['n_variaveis_avaliadas']}/{n['n_variaveis']})")
    for (u, a), ls in por_u.items():
        L.append(f"- {u} {a}: {', '.join(ls)}")
    nulos = Counter(v["local_id"] for v in model["valores"] if v["status"] == "a_medir")
    L += ["", "Valores a medir por local (local × variável): " +
          ", ".join(f"{nomes[k]} {n}" for k, n in nulos.items()) + "."]

    cur = model.get("_curadoria")
    if cur:
        L += ["", "## Curadoria das fontes (etl/config.py)", "",
              "A conferência acima usa as planilhas como estão. Depois dela, as fontes sem validação (Wikipedia, "
              "imprensa, sites sem revisão) saem e são trocadas por fontes da NASA, artigos revisados ou órgãos "
              "públicos; os valores que perderam a fonte são corrigidos e as notas, recalculadas.", "",
              "Fontes por classe: " + ", ".join(f"{k} {v}" for k, v in sorted(cur["por_classe"].items())) + ".", "",
              "| Fonte descartada | Motivo | Substituída por |", "|---|---|---|"]
        for d in cur["descartadas"]:
            L.append(f"| {d['id']} {d['referencia']} | {d['motivo']} | {', '.join(d['substituida_por']) or '—'} |")
        L += ["", "Valores corrigidos:", ""]
        for v in cur["valores_corrigidos"]:
            L.append(f"- {v['local_id']} › {v['variavel_id']}: {v['valor_planilha']} → "
                     f"{'a medir' if v['valor'] is None else v['valor']} ({', '.join(v['fonte_ids'])}). {v['motivo']}")
        L += ["", "Notas que mudaram em relação à planilha:", ""]
        for n in cur["notas_alteradas"]:
            L.append(f"- {nomes[n['local_id']]} › {n['item']} ({n['alvo_id']}): {n['planilha']} → {n['curadoria']}")

    L += ["", "## Decisões e observações preservadas", ""]
    for l in model["locais"]:
        if l["coordenada_aproximada"]:
            L.append(f"- **{l['nome']}**: coordenada aproximada — {l['coordenada_obs']}")
    for l in model["locais"]:
        if l["obs_dados"]:
            L.append(f"- {l['nome']} (dados): {l['obs_dados']}")
    disc = {}
    for c in model["catalogo_referencia"]:
        if c["status"] and c["status"].lower().startswith("discrep") and c["entidade_tipo"] == "local":
            disc.setdefault(c["variavel"], []).append(f"{nomes[c['entidade_id']]}: {c['valor_texto']}")
    for var, itens in disc.items():
        L.append(f"- Catálogo marca discrepância entre fontes em **{var}** — " + " | ".join(itens))
    for a in meta["avisos"]:
        L.append(f"- Aviso: {a}")
    return "\n".join(L) + "\n"


def _write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def write_all(model, res, validacao, site, gerado_em, out_dir=config.PROCESSED_DIR, site_path=config.SITE_JSON):
    validar_site(site)
    meta = {**model["metadata"], "versao_etl": ETL_VERSION, "gerado_em": gerado_em, "avisos": model["avisos"]}
    dados = {**{k: v for k, v in model.items() if not k.startswith("_")}, **res}
    arquivos = {}
    for nome, chave in TABELAS:
        arquivos[f"{nome}.json"] = _dumps(dados[chave])
        arquivos[f"csv/{nome}.csv"] = to_csv(dados[chave])
    bundle = {"metadata": meta, **{nome: dados[chave] for nome, chave in TABELAS}}
    arquivos["analogos.bundle.json"] = _dumps(bundle)
    arquivos["relatorio_validacao.json"] = _dumps(validacao)
    arquivos["relatorio_validacao.md"] = relatorio_md(meta, validacao, model, res)
    arquivos["metadata.json"] = _dumps(meta)
    if "_curadoria" in model:
        arquivos["curadoria_fontes.json"] = _dumps(model["_curadoria"])

    # Recria a pasta de saída do zero para não sobrar arquivo de uma versão anterior.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for rel, text in arquivos.items():
        _write_atomic(out_dir / rel, text)
    shutil.copyfile(config.SCHEMA_DOC, out_dir / "SCHEMA.md")
    _write_atomic(site_path, _dumps(site))
    return sorted(arquivos) + ["SCHEMA.md"]
