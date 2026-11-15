"""Transform: transforma as abas lidas no extract em tabelas normalizadas (formato longo, ids estáveis).

Por que formato longo: uma linha por fato (local × variável, local × utilidade × alvo...) em vez de uma
coluna por local. Assim, adicionar o 15º local não muda a estrutura de nenhum arquivo, e o front-end
filtra por `local_id` sem saber quantos locais existem.
"""
import re

from openpyxl.utils import get_column_letter

from . import config
from .text import (alvo_id, alvos_de, fonte_ids, fonte_ids_do_local, local_id, norm, parse_valor_texto,
                   sem_valor, slugify)


class ModelError(ValueError):
    """Inconsistência nas planilhas que impede gerar dados confiáveis."""


def _get(row, prefix):
    """Valor da coluna cujo cabeçalho começa com `prefix` (os cabeçalhos variam um pouco entre lotes)."""
    p = norm(prefix)
    for k, v in row.items():
        if isinstance(k, str) and norm(k).startswith(p):
            return v
    raise KeyError(f"coluna começando com {prefix!r} não encontrada em {list(row)}")


def _txt(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ---------------------------------------------------------------- utilidades e categorias

def utilidades(books, avisos):
    base = books["base-v1-1"]
    curtos = {}
    for _, r in base["Matriz por Utilidade"].table():
        curtos.setdefault(r["ID"], r["Utilidade"])
    out = []
    for _, r in base["Utilidades"].table():
        out.append({
            "id": r["ID"],
            "nome": _txt(r["Utilidade para a exploração"]),
            "nome_curto": _txt(curtos.get(r["ID"])),
            "aliases": [],
            "categoria_id": slugify(r["Categoria"]),
            "alvos": alvos_de(r["Alvo"]),
            "condicao": _txt(r["Condição que o alvo impõe"]),
            "variaveis_decisivas": _txt(r["Variáveis do catálogo que decidem"]),
            "criterio_aderencia": _txt(r["Critério de aderência"]),
        })
    # Os lotes repetem a aba Utilidades (sem as duas últimas colunas). Confere id, nome, categoria e alvo.
    por_id = {u["id"]: u for u in out}
    difere = {}
    for pid in ("lote-2", "lote-3"):
        for _, r in books[pid]["Utilidades"].table():
            u = por_id.get(r["ID"])
            if u is None or u["categoria_id"] != slugify(r["Categoria"]) or u["alvos"] != alvos_de(r["Alvo"]):
                raise ModelError(f"{pid}/Utilidades: {r['ID']} difere da base v1.1 (categoria ou alvo)")
            nome = _txt(r["Utilidade para a exploração"])
            if nome != u["nome"] and nome not in u["aliases"]:
                u["aliases"].append(nome)  # os lotes usam o nome sem o parêntese final
            if u["condicao"] != _txt(r["Condição que o alvo impõe"]):
                difere.setdefault(r["ID"], []).append(pid)
    if difere:
        avisos.append("Texto de 'Condição que o alvo impõe' nos lotes difere da base (usado o da base): "
                      + ", ".join(f"{u} ({' e '.join(p)})" for u, p in difere.items()))
    return out


def categorias_de(books, utils):
    nomes = {}
    for _, r in books["base-v1-1"]["Utilidades"].table():
        nomes.setdefault(slugify(r["Categoria"]), _txt(r["Categoria"]))
    out = []
    for cid, nome in nomes.items():
        us = [u for u in utils if u["categoria_id"] == cid]
        out.append({
            "id": cid,
            "nome": nome,
            "entra_na_aderencia": cid not in config.CATEGORIAS_FORA_DA_ADERENCIA,
            "utilidade_ids": [u["id"] for u in us],
            "n_utilidades_por_alvo": {a: sum(a in u["alvos"] for u in us) for a in config.ALVOS},
        })
    return out


# ---------------------------------------------------------------- variáveis e critérios

def variavel_id(nome, alvo=None):
    n = norm(nome)
    return (config.VARIAVEIS_OVERRIDE.get((n, alvo)) or config.VARIAVEIS_OVERRIDE.get((n, None))
            or slugify(nome))


CRIT_FIXAS = ["ID", "Alvo", "Variável", "Unidade / escala", "Valor no alvo", "Sentido",
              "Nota 3 se", "Nota 2 se", "Nota 1 se"]


def _criterios_da_planilha(book):
    sh = book["Critérios"]
    header = sh.header()
    if header[:9] != CRIT_FIXAS:
        raise ModelError(f"{book.id}/Critérios: cabeçalho inesperado {header[:9]}")
    cols_valor = [h for h in header[9:] if not h.startswith("Nota ") and h != "Por que essas faixas"]
    linhas = []
    for linha, r in sh.table():
        alvo = alvo_id(r["Alvo"])
        linhas.append({
            "linha_excel": linha,
            "utilidade_id": r["ID"],
            "alvo_id": alvo,
            "variavel_nome": _txt(r["Variável"]),
            "variavel_id": variavel_id(r["Variável"], alvo),
            "unidade": _txt(r["Unidade / escala"]),
            "valor_no_alvo": _txt(r["Valor no alvo"]),
            "sentido": _txt(r["Sentido"]),
            "faixas": {"nota_3": _num(r["Nota 3 se"]), "nota_2": _num(r["Nota 2 se"]), "nota_1": _num(r["Nota 1 se"])},
            "justificativa": _txt(r.get("Por que essas faixas")),
            "_valores": {local_id(c): r[c] for c in cols_valor},
            "_notas_excel": {local_id(h): r[h] for h in header if h.startswith("Nota ") and not h.endswith(" se")},
        })
    return linhas


def _assinatura(linhas):
    campos = ("utilidade_id", "alvo_id", "variavel_id", "variavel_nome", "unidade", "valor_no_alvo", "sentido", "faixas")
    return [tuple(str(l[c]) for c in campos) for l in linhas]


def criterios(books):
    """Um conjunto de critérios por grupo de planilhas (base-v1-1 e lotes-v1-1), 48 linhas cada."""
    por_conjunto, linhas_por_planilha = {}, {}
    for pid in config.LOTES:
        conj = config.PLANILHAS[pid]["conjunto"]
        linhas = _criterios_da_planilha(books[pid])
        linhas_por_planilha[pid] = linhas
        if conj in por_conjunto:
            ref_pid, ref = por_conjunto[conj]
            if _assinatura(ref) != _assinatura(linhas):
                raise ModelError(f"Critérios de {pid} diferem de {ref_pid}, mas os dois usam o conjunto {conj}. "
                                 "Crie um conjunto novo em etl/config.py.")
        else:
            por_conjunto[conj] = (pid, linhas)
    out = []
    for conj, (pid, linhas) in por_conjunto.items():
        for l in linhas:
            cid = f"{conj}.{l['utilidade_id']}.{l['alvo_id']}.{l['variavel_id']}"
            item = {k: v for k, v in l.items() if not k.startswith("_")}
            item.update(id=cid, conjunto_id=conj, planilha_origem=config.PLANILHAS[pid]["arquivo"], peso=1.0)
            if item["sentido"] not in ("maior", "menor"):
                raise ModelError(f"{cid}: sentido inválido {item['sentido']!r}")
            out.append(item)
    if len({c["id"] for c in out}) != len(out):
        raise ModelError("ids de critério repetidos")
    # Liga cada linha lida (de cada planilha) ao id do critério, para o validate.
    for pid, linhas in linhas_por_planilha.items():
        conj = config.PLANILHAS[pid]["conjunto"]
        for l in linhas:
            l["criterio_id"] = f"{conj}.{l['utilidade_id']}.{l['alvo_id']}.{l['variavel_id']}"
    return out, linhas_por_planilha


def conjuntos(crits):
    out = {}
    for c in crits:
        cj = out.setdefault(c["conjunto_id"], {"id": c["conjunto_id"], "planilha_origem": c["planilha_origem"],
                                               "planilhas": [], "n_criterios": 0})
        cj["n_criterios"] += 1
    for pid in config.LOTES:
        out[config.PLANILHAS[pid]["conjunto"]]["planilhas"].append(config.PLANILHAS[pid]["arquivo"])
    return list(out.values())


# ---------------------------------------------------------------- locais e alvos

def locais_e_alvos(books):
    rede = {local_id(r["Local"]): r for _, r in books["rede"]["Locais"].table()}
    if set(rede) != set(config.LOCAIS):
        raise ModelError(f"Rede/Locais não tem os 14 locais: {sorted(set(config.LOCAIS) ^ set(rede))}")
    info, alvos = {}, []
    for _, r in books["base-v1-1"]["Locais"].table():
        corpo = norm(r["Corpo"])
        if corpo == "terra":
            info[local_id(r["Local"])] = {
                "nome_completo": _txt(r["Local"]), "recorte": _txt(r["Recorte (escala)"]),
                "lat": r["Latitude"], "lon": r["Longitude"], "por_que_recorte": _txt(r["Por que este recorte"]),
                "justificativa": None, "obs_dados": None, "lote": "base-v1-1", "listado_planilha": None,
            }
        else:
            aid = alvo_id(r["Local"])
            alvos.append({
                "id": aid, "nome": _txt(r["Local"]), "corpo": config.ALVOS[aid]["corpo"],
                "local_referencia": config.ALVOS[aid]["local_referencia"],
                "lat": _num(r["Latitude"]), "lon": _num(r["Longitude"]),
                "recorte": _txt(r["Recorte (escala)"]), "por_que_recorte": _txt(r["Por que este recorte"]),
            })
    for pid in ("lote-2", "lote-3"):
        for _, r in books[pid]["Locais"].table():
            info[local_id(r["Local"])] = {
                "nome_completo": _txt(r["Local"]), "recorte": _txt(_get(r, "Recorte")),
                "lat": r["Latitude"], "lon": r["Longitude"], "por_que_recorte": None,
                "justificativa": _txt(_get(r, "Por que é análogo")), "obs_dados": _txt(_get(r, "Observação")),
                "lote": pid, "listado_planilha": _txt(_get(r, "Listado") if any(norm(k).startswith("listado") for k in r)
                                                      else _get(r, "Proposto")),
            }
    leituras = {}
    for _, r in books["base-v1-1"]["Leitura preliminar"].table():
        leituras.setdefault(local_id(r["Local na Terra"]), []).append({
            "alvo_id": alvo_id(r["Alvo"]), "grau_hipotese": _txt(r["Grau (hipótese)"]),
            "similar_em": _txt(r["É similar em"]), "diferente_em": _txt(r["É diferente em"]),
            "utilidade": _txt(r["Utilidade para a exploração"]),
        })

    out = []
    for lid, aliases in config.LOCAIS.items():
        i, rd = info[lid], rede[lid]
        listado = alvos_de(rd["Listado como análogo de"])
        if i["listado_planilha"] and alvos_de(i["listado_planilha"]) != listado:
            raise ModelError(f"{lid}: 'listado como' difere entre o lote e a rede")
        planilha_rede = {v["rotulo"]: k for k, v in config.PLANILHAS.items()}[_txt(rd["Planilha"])]
        if planilha_rede != i["lote"]:
            raise ModelError(f"{lid}: a rede diz {rd['Planilha']}, mas o local está em {i['lote']}")
        lat, lon, aprox, obs_coord = _num(i["lat"]), _num(i["lon"]), False, None
        if lid in config.COORDENADAS_OVERRIDE:
            ov = config.COORDENADAS_OVERRIDE[lid]
            lat, lon, aprox, obs_coord = ov["lat"], ov["lon"], True, ov["motivo"]
        elif i["obs_dados"] and "aproximad" in norm(i["obs_dados"]):
            aprox, obs_coord = True, i["obs_dados"]
        if lat is None or lon is None:
            raise ModelError(f"{lid}: sem coordenadas numéricas ({i['lat']!r}, {i['lon']!r})")
        out.append({
            "id": lid,
            "nome": _txt(rd["Local"]),
            "nome_completo": i["nome_completo"],
            "aliases": aliases,
            "pais": _txt(rd["País"]),
            "lote": i["lote"],
            "conjunto_criterios": config.PLANILHAS[i["lote"]]["conjunto"],
            "listado_como": listado,
            "lat": lat,
            "lon": lon,
            "coordenada_aproximada": aprox,
            "coordenada_obs": obs_coord,
            "recorte": i["recorte"],
            "por_que_recorte": i["por_que_recorte"],
            "justificativa": i["justificativa"],
            "obs_dados": i["obs_dados"],
            "fonte_ids": fonte_ids(i["justificativa"]),
            "leitura_qualitativa": leituras.get(lid, []),
        })
    return out, alvos


# ---------------------------------------------------------------- valores (local × variável)

def _status_texto(valor, fonte_quando_vazio):
    """Texto original que explica a ausência ('A extrair (MODIS)'), vindo da célula ou da coluna Fonte."""
    if isinstance(valor, str) and valor.strip():
        return valor.strip()
    if fonte_quando_vazio and norm(fonte_quando_vazio).startswith(("a extrair", "a medir", "a verificar")):
        return fonte_quando_vazio
    return None


def valores(books, crit_linhas, locais):
    nomes = {l["id"]: l["aliases"] for l in locais}
    out = {}

    def add(rec):
        key = (rec["local_id"], rec["variavel_id"])
        if key in out:
            a, b = out[key]["valor"], rec["valor"]
            if a != b:
                raise ModelError(f"{key}: valores diferentes na mesma planilha ({a} × {b})")
            return
        out[key] = rec

    # Base: valores digitados direto nas linhas da aba Critérios (J:L).
    base = books["base-v1-1"]
    header = base["Critérios"].header()
    for l in crit_linhas["base-v1-1"]:
        for lid, v in l["_valores"].items():
            col = next(i for i, h in enumerate(header, 1) if h.endswith("(valor)") and local_id(h) == lid)
            vazio = sem_valor(v)
            add({
                "local_id": lid, "variavel_id": l["variavel_id"],
                "valor": None if vazio else _num(v),
                "status": "a_medir" if vazio else "com_valor",
                "status_texto": _txt(v) if isinstance(v, str) else None,
                "fonte_ids": [], "fonte_texto": None,
                "observacao": "Valor digitado na aba Critérios da base; as fontes por variável estão no Catálogo.",
                "origem": f"{base.path.name} › Critérios!{get_column_letter(col)}{l['linha_excel']}",
            })

    # Lotes: aba Valores, uma linha por variável e uma coluna por local.
    for pid in ("lote-2", "lote-3"):
        sh = books[pid]["Valores"]
        header = sh.header()
        locs = [h for h in header[2:] if h not in ("Fonte", "Observação")]
        for linha, r in sh.table():
            vid = variavel_id(r["Variável"])
            for nome in locs:
                lid = local_id(nome)
                v = r[nome]
                vazio = sem_valor(v)
                if not vazio and _num(v) is None:
                    raise ModelError(f"{pid}/Valores linha {linha}: valor não numérico {v!r} em {nome}")
                fonte = _txt(r["Fonte"])
                add({
                    "local_id": lid, "variavel_id": vid,
                    "valor": None if vazio else _num(v),
                    "status": "a_medir" if vazio else "com_valor",
                    "status_texto": _status_texto(v, fonte if vazio else None),
                    "fonte_ids": fonte_ids_do_local(fonte, nomes[lid]),
                    "fonte_texto": fonte,
                    "observacao": _txt(r["Observação"]),
                    "origem": f"{books[pid].path.name} › Valores!{get_column_letter(header.index(nome) + 1)}{linha}",
                    "_nome_variavel": _txt(r["Variável"]), "_unidade": _txt(r["Unidade"]),
                })
    return list(out.values())


def variaveis(crits, vals):
    out = {}
    for c in crits:
        v = out.setdefault(c["variavel_id"], {"id": c["variavel_id"], "nomes": [], "unidades": [], "conjuntos": []})
        for campo, valor in (("nomes", c["variavel_nome"]), ("unidades", c["unidade"]), ("conjuntos", c["conjunto_id"])):
            if valor not in v[campo]:
                v[campo].append(valor)
    for r in vals:
        nome = r.pop("_nome_variavel", None)
        unidade = r.pop("_unidade", None)
        if nome:
            v = out.setdefault(r["variavel_id"], {"id": r["variavel_id"], "nomes": [], "unidades": [], "conjuntos": []})
            if nome in v["nomes"]:
                v["nomes"].remove(nome)
            v["nomes"].insert(0, nome)  # o nome da aba Valores (lotes) é o mais descritivo
            if unidade and unidade not in v["unidades"]:
                v["unidades"].append(unidade)
    res = []
    for vid, v in out.items():
        unidade, obs = config.UNIDADE_OVERRIDE.get(vid, (None, None))
        if unidade is None:
            if len(v["unidades"]) > 1:
                raise ModelError(f"Variável {vid} com unidades diferentes {v['unidades']}: defina UNIDADE_OVERRIDE")
            unidade = v["unidades"][0] if v["unidades"] else None
        res.append({
            "id": vid,
            "nome": v["nomes"][0],
            "aliases": v["nomes"],
            "unidade": unidade,
            "tipo": "escala_0_3" if unidade and "escala" in norm(unidade) else "numerico",
            "conjuntos": v["conjuntos"],
            "observacao": obs,
        })
    return res


# ---------------------------------------------------------------- catálogo, fontes, textos, validação

def catalogo(books):
    sh = books["base-v1-1"]["Catálogo"]
    header = sh.header()
    entidades = []
    for h in header[3:]:
        if h in ("Status", "Dataset para extrair", "Fontes"):
            break
        try:
            entidades.append((h, local_id(h), "local"))
        except KeyError:
            entidades.append((h, alvo_id(h), "alvo"))
    out = []
    for linha, r in sh.table():
        for h, eid, tipo in entidades:
            bruto = r[h]
            parsed = parse_valor_texto(bruto if not sem_valor(bruto) else None)
            parsed["valor_texto"] = _txt(bruto)
            out.append({
                "variavel_id": slugify(r["Variável"]),
                "dimensao": _txt(r["Dimensão"]),
                "variavel": _txt(r["Variável"]),
                "unidade": _txt(r["Unidade"]),
                "entidade_id": eid,
                "entidade_tipo": tipo,
                **parsed,
                "a_medir": sem_valor(bruto),
                "status": _txt(r["Status"]),
                "dataset": _txt(r["Dataset para extrair"]),
                "fonte_ids": fonte_ids(r["Fontes"]),
                "fonte_texto": _txt(r["Fontes"]),
                "origem": f"Catálogo!{get_column_letter(header.index(h) + 1)}{linha}",
            })
    return out


def fontes(books):
    out = []
    for pid, meta in config.PLANILHAS.items():
        for _, r in books[pid]["Fontes"].table():
            if pid == "rede":
                out.append({"id": r["ID"], "planilha_id": pid, "planilha": meta["arquivo"],
                            "referencia": _txt(r["Planilha"]), "fornece": _txt(r["O que fornece"]),
                            "link": None, "observacao": _txt(r["Referências"])})
            else:
                out.append({"id": r["ID"], "planilha_id": pid, "planilha": meta["arquivo"],
                            "referencia": _txt(r["Referência"]), "fornece": _txt(r["O que fornece"]),
                            "link": _txt(r["Link"]), "observacao": None})
    if len({f["id"] for f in out}) != len(out):
        raise ModelError("ids de fonte repetidos entre planilhas")
    return out


BLOCOS_TEXTO = {
    "base-v1-1": ["Como o coeficiente é calculado", "Histórico de mudanças"],
    "lote-2": ["Cuidados ao ler", "Leitura dos resultados"],
    "lote-3": ["Cuidados ao ler", "Leitura dos resultados"],
    "rede": ["Conclusão", "Cuidados ao ler"],
}


def _limpa_marcador(s):
    return re.sub(r"^(•|\d+\.)\s*", "", s).strip()


def textos(books):
    out = []
    for pid, titulos in BLOCOS_TEXTO.items():
        sh = books[pid]["Resumo"]
        intro = [str(sh.cell(r, 1)).strip() for r in (config.ROW_HEADER, config.ROW_HEADER + 1) if sh.cell(r, 1)]
        out.append({"planilha_id": pid, "aba": "Resumo", "bloco": "introducao", "titulo": None,
                    "linhas": intro})
        for t in titulos:
            b = sh.text_block(t)
            out.append({"planilha_id": pid, "aba": "Resumo", "bloco": slugify(b["titulo"]), "titulo": b["titulo"],
                        "linhas": [_limpa_marcador(x) for x in b["linhas"]]})
    return out


def validacao_literatura(books):
    sh = books["base-v1-1"]["Validação"]
    out = []
    for i, (linha, r) in enumerate(sh.table(), 1):
        m = re.match(r"^(U\d{2})\s+(.*)$", str(r["Utilidade"]))
        alvo_txt = str(r["Alvo"])
        out.append({
            "id": f"V{i:02d}",
            "local_id": local_id(r["Local"]),
            "alvos": [alvo_id(a.strip()) for a in alvo_txt.split("×")],
            "utilidade_id": m.group(1) if m else None,
            "descricao": m.group(2) if m else _txt(r["Utilidade"]),
            "literatura": _txt(r["O que a literatura diz"]),
            "fonte_ids": fonte_ids(r["Fonte"]),
            "expectativa": _txt(r["Expectativa"]),
            "linha_excel": linha,
        })
    return out


def leituras_matriz(books):
    """Texto 'Leitura' da Matriz por Utilidade da base, por utilidade × alvo (fala dos 3 locais da base)."""
    out = {}
    for _, r in books["base-v1-1"]["Matriz por Utilidade"].table():
        out[(r["ID"], alvo_id(r["Alvo"]))] = _txt(_get(r, "Leitura"))
    return out


def metadata(books, arquivos):
    base = books["base-v1-1"]["Resumo"]
    versao = None
    for r in range(config.ROW_HEADER, config.ROW_HEADER + 5):
        v = base.cell(r, 1)
        if isinstance(v, str) and v.startswith("Base de referência"):
            versao = v
    return {
        "modelo": versao,
        "data_planilhas": books["rede"]["Resumo"].data,
        "arquivos_origem": arquivos,
        "escala": {"min": 0, "max": 3, "descricao": "0 = não serve, 3 = forte. null = a medir (não entra na média)."},
    }


def build(books, arquivos):
    avisos = []
    utils = utilidades(books, avisos)
    crits, crit_linhas = criterios(books)
    locs, alvs = locais_e_alvos(books)
    vals = valores(books, crit_linhas, locs)
    return {
        "metadata": metadata(books, arquivos),
        "locais": locs,
        "alvos": alvs,
        "utilidades": utils,
        "categorias": categorias_de(books, utils),
        "variaveis": variaveis(crits, vals),
        "conjuntos": conjuntos(crits),
        "criterios": crits,
        "valores": vals,
        "catalogo_referencia": catalogo(books),
        "fontes": fontes(books),
        "textos": textos(books),
        "validacao_casos": validacao_literatura(books),
        "_leituras": leituras_matriz(books),
        "_crit_linhas": crit_linhas,
        "avisos": avisos,
    }
