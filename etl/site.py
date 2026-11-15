"""Monta o web/data/analogs.json (contrato v2 com o front-end 3D) a partir do modelo recalculado.

O front-end não calcula nada: cada número e cada frase que aparece na tela sai daqui.
- targets  = os 2 alvos (Lua – Shackleton, Marte – Jezero), pontos nos globos da Lua e de Marte.
- analogs  = os 14 locais da Terra, pontos no globo da Terra (com a foto e o crédito de config.IMAGENS).
- links    = 14 × 2 ligações (todo local é avaliado contra os dois alvos). `score` = aderência ÷ 3.
- dimensions = as categorias de utilidade; "Limitações universais" aparece, mas não entra no score.
Os ids são os mesmos de data/processed (local_id, alvo_id, utilidade_id), para cruzar os dois.
"""
import re

from . import config
from .text import norm

ROUND = 4


def _r(x):
    return None if x is None else round(float(x), ROUND)


def fmt(x):
    """Número para texto em pt-BR: 1.5 -> '1,5'; 3.0 -> '3'; 0.6667 -> '0,67'."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _ordem_fonte(fid):
    return ("FGHRN".index(fid[0]), int(fid[1:]))


def _fontes_do_local(local, model):
    ids = set(local["fonte_ids"])
    if local["lote"] == "base-v1-1":
        for c in model["catalogo_referencia"]:
            if c["entidade_id"] == local["id"] and not c["a_medir"]:
                ids.update(c["fonte_ids"])
        for v in model["validacao_casos"]:
            if v["local_id"] == local["id"]:
                ids.update(v["fonte_ids"])
    else:
        for v in model["valores"]:
            if v["local_id"] == local["id"] and v["status"] == "com_valor":
                ids.update(v["fonte_ids"])
    por_id = {f["id"]: f for f in model["fontes"]}
    out = []
    for fid in sorted(ids, key=_ordem_fonte):
        f = por_id.get(fid)
        if f and f.get("classe") != "descartada" and f["link"] and f["link"].startswith("http"):
            out.append({"id": fid, "label": f["referencia"], "url": f["link"], "kind": f["classe"]})
    return out


def _por_corpo(texto):
    """'Terra: MODIS LST | Lua: Diviner | Marte: MEDA' -> {'terra': ..., 'lua': ..., 'marte': ...}.
    Texto sem prefixo de corpo (ex.: 'Literatura') vale para a Terra."""
    if not texto:
        return {}
    out = {}
    for parte in texto.split("|"):
        parte = parte.strip()
        corpo, sep, resto = parte.partition(":")
        chave = corpo.strip().lower()
        if sep and chave in ("terra", "lua", "marte"):
            out[chave] = resto.strip()
        elif parte:
            out.setdefault("terra", parte)
    return out


def _condicao_do_alvo(texto, alvo_id):
    """'Lua: crateras a ~40 K. Marte: noites a −83 °C' -> só o trecho do alvo (ou o texto inteiro)."""
    if not texto:
        return None
    partes = re.split(r"(?:^|[.;]\s*)(Lua|Marte)\s*:\s*", texto)
    trechos = {partes[i].lower(): partes[i + 1].strip().rstrip(".;") for i in range(1, len(partes) - 1, 2)}
    return trechos.get(alvo_id) or texto


def _apelidos(local_id):
    return [norm(n) for n in config.LOCAIS[local_id] + config.APELIDOS_OBSERVACAO.get(local_id, [])]


def _observacao_do_local(texto, local_id):
    """Só o trecho da observação que vale para o local. 'McMurdo: X. Mauna Kea: Y' -> 'X' para McMurdo.
    Trechos sem prefixo de local valem para todos; trechos de outros locais saem. Sem nada -> None."""
    if not texto:
        return None
    todos = {lid: _apelidos(lid) for lid in config.LOCAIS}
    proprios, gerais = [], []
    for trecho in re.split(r"(?<=[.;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", texto.strip()):
        prefixo, sep, resto = trecho.partition(":")
        if sep and len(prefixo) <= 45:
            p = norm(prefixo)
            donos = {lid for lid, nomes in todos.items() if any(n and n in p for n in nomes)}
            if donos:
                if local_id in donos:
                    proprios.append(resto.strip())
                continue
        gerais.append(trecho.strip())
    out = " ".join(proprios + gerais).strip()
    return out or None


def _com_correcao(obs, val):
    """Acrescenta à observação o motivo da correção feita na curadoria das fontes (se houver)."""
    cor = (val or {}).get("correcao")
    if not cor:
        return obs
    return f"{obs}. Revisão das fontes: {cor}" if obs else f"Revisão das fontes: {cor}"


def _evidencias(local, alvo_id, utilidade_id, ctx):
    """Uma linha por variável que entra na nota da utilidade: valor no local, valor no alvo, faixas,
    nota da variável, fontes e dataset de referência. Tudo vem das planilhas."""
    out = []
    for c in ctx["criterios"].get((local["conjunto_criterios"], utilidade_id, alvo_id), []):
        nv = ctx["notas_variavel"].get((local["id"], c["id"]))
        val = ctx["valores"].get((local["id"], c["variavel_id"]))
        cat_id = config.VARIAVEL_CATALOGO.get(c["variavel_id"])
        if local["lote"] == "base-v1-1":
            # Base: valores digitados na aba Critérios, sem fonte; as fontes da variável estão no Catálogo.
            cat = ctx["catalogo"].get((local["id"], cat_id)) if cat_id else None
            fonte_ids, escopo = (cat["fonte_ids"] if cat else []), "catalogo"
        else:
            fonte_ids, escopo = (val["fonte_ids"] if val else []), "local"
        if val and val.get("correcao"):
            fonte_ids, escopo = val["fonte_ids"], "local"  # valor corrigido na curadoria: a fonte é deste local
        datasets = _por_corpo(ctx["dataset"].get(cat_id)) if cat_id else {}
        fontes = [fid for fid in fonte_ids if fid in ctx["fontes"]]
        ctx["usadas"].update(fontes)
        faixas = c["faixas"] or {}
        out.append({
            "variable": c["variavel_nome"], "unit": c["unidade"],
            "value": nv["valor"] if nv else None,
            "value_note": (val or {}).get("status_texto") if not nv or nv["valor"] is None else None,
            "note": nv["nota"] if nv else None,
            "level": config.nivel(nv["nota"] if nv else None),
            "status": nv["status"] if nv else "a_medir",
            "direction": c["sentido"],
            "thresholds": None if faixas.get("nota_3") is None else
                {"3": faixas["nota_3"], "2": faixas["nota_2"], "1": faixas["nota_1"]},
            "target_value": c["valor_no_alvo"],
            "observation": _com_correcao(_observacao_do_local((val or {}).get("observacao"), local["id"])
                                         if local["lote"] != "base-v1-1" else None, val),
            "sources": fontes, "sources_scope": escopo,
            "dataset_earth": datasets.get("terra"), "dataset_target": datasets.get(alvo_id),
        })
    return out


def _imagem(local_id):
    """Foto do local (etl/config.py › IMAGENS) no formato do site. Falha se faltar entrada ou arquivo."""
    img = config.IMAGENS.get(local_id)
    if img is None:
        raise ValueError(f"Local sem imagem em config.IMAGENS: {local_id}")
    arquivo = config.IMAGENS_DIR / f"{local_id}.jpg"
    if not arquivo.is_file():
        raise FileNotFoundError(f"Imagem do local {local_id} não encontrada: {arquivo}")
    return {
        "src": f"{config.IMAGENS_URL}/{local_id}.jpg", "alt": img["alt"], "caption": img["legenda"],
        "kind": img["tipo"],
        "credit": {"author": img["autor"], "license": img["licenca"], "license_url": img["licenca_url"],
                   "source_url": img["fonte"]},
    }


def build(model, res, gerado_em):
    utils = {u["id"]: u for u in model["utilidades"]}
    cats = {c["id"]: c for c in model["categorias"]}
    nu = {(n["local_id"], n["utilidade_id"], n["alvo_id"]): n for n in res["notas_utilidade"]}
    nc = {(n["local_id"], n["categoria_id"], n["alvo_id"]): n for n in res["notas_categoria"]}
    ad = {(a["local_id"], a["alvo_id"]): a for a in res["aderencia"]}
    melhor = {(m["utilidade_id"], m["alvo_id"]): m for m in res["melhor_por_utilidade"]}
    pares = [(m["utilidade_id"], m["alvo_id"]) for m in res["melhor_por_utilidade"]]
    criterios = {}
    for c in model["criterios"]:
        criterios.setdefault((c["conjunto_id"], c["utilidade_id"], c["alvo_id"]), []).append(c)
    dataset = {}
    for c in model["catalogo_referencia"]:
        dataset.setdefault(c["variavel_id"], c["dataset"])
    ctx = {
        "criterios": criterios,
        "notas_variavel": {(n["local_id"], n["criterio_id"]): n for n in res["notas_variavel"]},
        "valores": {(v["local_id"], v["variavel_id"]): v for v in model["valores"]},
        "catalogo": {(c["entidade_id"], c["variavel_id"]): c for c in model["catalogo_referencia"]},
        "dataset": dataset,
        "fontes": {f["id"]: f for f in model["fontes"] if f.get("classe") != "descartada"},
        "usadas": set(),
    }

    targets = [{
        "id": a["id"], "body": a["corpo"], "name": a["nome"], "short_name": a["local_referencia"],
        "lat": a["lat"], "lon": a["lon"], "description": a["por_que_recorte"] or "", "clipping": a["recorte"],
    } for a in model["alvos"]]

    analogs, links = [], []
    for l in model["locais"]:
        a0 = ad[(l["id"], "lua")]
        analogs.append({
            "id": l["id"], "name": l["nome"], "full_name": l["nome_completo"], "country": l["pais"],
            "lat": l["lat"], "lon": l["lon"], "approximate_coords": l["coordenada_aproximada"],
            "description": l["justificativa"] or l["por_que_recorte"] or l["recorte"] or "",
            "narrative": config.NARRATIVAS.get(l["id"]),
            "clipping": l["recorte"], "data_notes": l["obs_dados"],
            "listed_as": l["listado_como"], "batch": config.PLANILHAS[l["lote"]]["rotulo"],
            "model_indicates": a0["modelo_indica"], "matches_listing": a0["bate"],
            "image": _imagem(l["id"]),
        })
        fontes = _fontes_do_local(l, model)
        leituras = {q["alvo_id"]: q for q in l["leitura_qualitativa"]}
        for t in model["alvos"]:
            a = t["id"]
            row = ad[(l["id"], a)]
            if row["aderencia"] is None:
                continue  # sem nenhuma utilidade avaliada: não há o que ligar (nunca inventar 0)
            dims = {}
            for cid in cats:
                n = nc.get((l["id"], cid, a))
                if n and n["nota"] is not None:
                    dims[cid] = {"score": _r(n["nota"] / 3), "adherence": _r(n["nota"]), "level": config.nivel(n["nota"]),
                                 "evaluated": n["n_avaliadas_local"], "total": n["n_utilidades"]}
            us = []
            for (u, al) in pares:
                if al != a:
                    continue
                n = nu[(l["id"], u, a)]
                m = melhor[(u, a)]
                us.append({
                    "id": u, "name": utils[u]["nome_curto"], "category": utils[u]["categoria_id"],
                    "adherence": _r(n["nota"]), "score": _r(None if n["nota"] is None else n["nota"] / 3),
                    "level": config.nivel(n["nota"]),
                    "status": n["status"],
                    "variables_evaluated": n["n_variaveis_avaliadas"], "variables_total": n["n_variaveis"],
                    "best_in_network": bool(m["melhor_nota"] is not None and m["melhor_nota"] >= 2
                                            and l["id"] in m["empatados"]),
                    "reading": n["leitura"],
                    "meaning": {
                        "purpose": utils[u]["nome"],
                        "condition": _condicao_do_alvo(utils[u]["condicao"], a),
                        "criterion": utils[u]["criterio_aderencia"],
                    },
                    "evidence": _evidencias(l, a, u, ctx),
                })
            avaliadas = [x for x in us if x["adherence"] is not None]
            strengths, limits = [], []
            q = leituras.get(a)
            ponto = lambda x: {"kind": "utility", "id": x["id"], "name": x["name"], "category": x["category"],
                               "adherence": x["adherence"], "level": x["level"]}
            if q and q["similar_em"]:
                strengths.append({"kind": "reading", "label": "Parecido em", "text": q["similar_em"]})
            for x in sorted(avaliadas, key=lambda x: (-x["adherence"], x["id"])):
                if x["adherence"] >= config.LIMIAR_FORTE:
                    strengths.append(ponto(x))
            if q and q["diferente_em"]:
                limits.append({"kind": "reading", "label": "Diferente em", "text": q["diferente_em"]})
            for x in sorted(avaliadas, key=lambda x: (x["adherence"], x["id"])):
                if x["adherence"] <= config.LIMIAR_FRACO:
                    limits.append(ponto(x))
            if not limits:
                limits.append({"kind": "reading", "label": "Observação",
                               "text": "Nenhuma utilidade avaliada ficou com nota ≤ 1; veja as utilidades a medir."})
            links.append({
                "analog": l["id"], "target": a,
                "score": _r(row["aderencia"] / 3),
                "adherence": _r(row["aderencia"]),
                "level": config.nivel(row["aderencia"]),
                "rank": row["rank"],
                "rank_tied": row["rank_empatado"],
                "listed_as_target": a in l["listado_como"],
                "dimensions": dims,
                "utilities": us,
                "strengths": strengths,
                "limits": limits,
                "to_measure": [x["name"] for x in us if x["status"] == "a_medir"],
                "best_in_network_count": row["n_melhor_em"],
                "exploration_use": (q["utilidade"] if q and q["utilidade"] else l["justificativa"]) or "",
                "sources": fontes,
            })

    textos_rede = {t["bloco"]: t for t in model["textos"] if t["planilha_id"] == "rede"}
    return {
        "version": 2,
        "generated_at": gerado_em,
        "model": {
            "name": model["metadata"]["modelo"],
            "data_date": model["metadata"]["data_planilhas"],
            "scale": "Aderência de 0 a 3 (0 = não serve, 3 = forte); score = aderência ÷ 3. "
                     "Utilidade sem nota = a medir (não entra na média).",
            "excluded_from_score": sorted(config.CATEGORIAS_FORA_DA_ADERENCIA),
        },
        "dimensions": [{"id": c["id"], "label": c["nome"], "in_score": c["entra_na_aderencia"]}
                       for c in model["categorias"]],
        "targets": targets,
        "analogs": analogs,
        "links": links,
        "source_index": {fid: {"label": ctx["fontes"][fid]["referencia"],
                               "url": ctx["fontes"][fid]["link"] if (ctx["fontes"][fid]["link"] or "").startswith("http") else None,
                               "kind": ctx["fontes"][fid]["classe"]}
                         for fid in sorted(ctx["usadas"], key=_ordem_fonte)},
        "network": {
            "coverage": [{"target": c["alvo_id"], "evaluated": c["avaliadas"], "covered": c["cobertas"],
                          "gaps": c["lacunas"], "to_measure": c["a_medir"]} for c in res["cobertura"]],
            "best_by_utility": [{
                "utility": m["utilidade_id"], "name": utils[m["utilidade_id"]]["nome_curto"], "target": m["alvo_id"],
                "best_score": _r(m["melhor_nota"]), "best": m["empatados"], "status": m["situacao"],
            } for m in res["melhor_por_utilidade"]],
            "conclusions": [x for k, t in textos_rede.items() if k.startswith("conclusao") for x in t["linhas"]],
            "caveats": textos_rede.get("cuidados-ao-ler", {}).get("linhas", []),
        },
    }
