"""Validate: compara, célula a célula, o que o Python recalculou com o que o Excel guardou em cache.

Se as fórmulas foram reproduzidas corretamente, não há divergência. Uma divergência significa uma de três
coisas: a regra em Python está errada, a planilha foi editada sem recalcular (cache velho), ou a planilha
tem um erro. O relatório aponta a aba e a chave para conferir.
"""
from . import config
from .text import alvo_id, local_id, norm

TOL = 1e-9


def _norm_excel(v):
    """Excel guarda '' (fórmula que devolve vazio) e '—' para 'sem valor'. Ambos viram None."""
    if isinstance(v, str) and v.strip() in ("", "—"):
        return None
    return v


def _igual(excel, py):
    excel = _norm_excel(excel)
    if excel is None or py is None:
        return excel is None and py is None
    if isinstance(py, bool) or isinstance(excel, bool):
        return excel == py
    if isinstance(py, (int, float)) and isinstance(excel, (int, float)):
        return abs(float(excel) - float(py)) <= TOL
    return str(excel).strip() == str(py).strip()


class Comparador:
    def __init__(self):
        self.itens = []

    def cmp(self, planilha, aba, chave, campo, excel, py):
        ok = _igual(excel, py)
        self.itens.append({"planilha_id": planilha, "aba": aba, "chave": chave, "campo": campo,
                           "excel": _norm_excel(excel), "recalculado": py, "ok": ok})

    def resumo(self):
        por_aba = {}
        for i in self.itens:
            k = f"{config.PLANILHAS[i['planilha_id']]['arquivo']} › {i['aba']}"
            d = por_aba.setdefault(k, {"comparadas": 0, "divergencias": 0})
            d["comparadas"] += 1
            d["divergencias"] += 0 if i["ok"] else 1
        return {
            "tolerancia": TOL,
            "comparadas": len(self.itens),
            "divergencias": sum(not i["ok"] for i in self.itens),
            "por_aba": por_aba,
            "lista_divergencias": [i for i in self.itens if not i["ok"]],
        }


def _rotulo_alvo(a):
    return {"lua": "Lua", "marte": "Marte", "empate": "Empate"}[a] if a else None


def run(books, model, res):
    c = Comparador()
    nv = {(n["local_id"], n["criterio_id"]): n for n in res["notas_variavel"]}
    nu = {(n["local_id"], n["utilidade_id"], n["alvo_id"]): n["nota"] for n in res["notas_utilidade"]}
    nc = {(n["local_id"], n["categoria_id"], n["alvo_id"]): n for n in res["notas_categoria"]}
    ad = {(a["local_id"], a["alvo_id"]): a for a in res["aderencia"]}
    locais_por_lote = {pid: [l["id"] for l in model["locais"] if l["lote"] == pid] for pid in config.LOTES}

    # 1. Critérios: valores puxados (lotes) e notas por variável
    for pid, linhas in model["_crit_linhas"].items():
        for l in linhas:
            for lid, excel in l["_notas_excel"].items():
                n = nv[(lid, l["criterio_id"])]
                chave = f"{l['criterio_id']} | {lid}"
                c.cmp(pid, "Critérios", chave, "nota", excel, n["nota"])
                if pid != "base-v1-1":
                    c.cmp(pid, "Critérios", chave, "valor (INDEX/MATCH da aba Valores)", l["_valores"][lid], n["valor"])

    # 2. Matriz por Utilidade e Matriz por Categoria de cada planilha
    from .transform import slugify
    for pid in config.LOTES:
        for _, r in books[pid]["Matriz por Utilidade"].table():
            for lid in locais_por_lote[pid]:
                nome = next(h for h in r if isinstance(h, str) and _eh_local(h, lid))
                c.cmp(pid, "Matriz por Utilidade", f"{r['ID']} | {r['Alvo']} | {lid}", "nota", r[nome],
                      nu[(lid, r["ID"], alvo_id(r["Alvo"]))])
        for _, r in books[pid]["Matriz por Categoria"].table():
            cid, a = slugify(r["Categoria"]), alvo_id(r["Alvo"])
            for lid in locais_por_lote[pid]:
                nome = next(h for h in r if isinstance(h, str) and _eh_local(h, lid))
                c.cmp(pid, "Matriz por Categoria", f"{cid} | {a} | {lid}", "nota", r[nome], nc[(lid, cid, a)]["nota"])
            c.cmp(pid, "Matriz por Categoria", f"{cid} | {a}", "utilidades na categoria",
                  r["Utilidades na categoria"], nc[(locais_por_lote[pid][0], cid, a)]["n_utilidades"])
            col = "Utilidades já avaliadas (algum local)"
            if col in r:  # só a base tem; conta só os locais da própria planilha
                us = [u["id"] for u in model["utilidades"] if u["categoria_id"] == cid and a in u["alvos"]]
                py = sum(any(nu[(lid, u, a)] is not None for lid in locais_por_lote[pid]) for u in us)
                c.cmp(pid, "Matriz por Categoria", f"{cid} | {a}", "utilidades já avaliadas", r[col], py)

    # 3. Resumo da base: aderência, nº de notas 3, nº a medir
    sh = books["base-v1-1"]["Resumo"]
    for titulo, campo in (("Aderência média", "aderencia"), ("Utilidades com nota 3", "n_fortes"),
                          ("Utilidades ainda a medir", "n_a_medir")):
        for _, r in sh.block_table(titulo):
            a = alvo_id(r["Alvo"])
            for nome in [k for k in r if k != "Alvo" and k is not None]:
                lid = local_id(nome)
                c.cmp("base-v1-1", "Resumo", f"{titulo} | {a} | {lid}", campo, r[nome], ad[(lid, a)][campo])

    # 4. Resumo dos lotes: aderência, o modelo indica, bate?
    for pid in ("lote-2", "lote-3"):
        for _, r in books[pid]["Resumo"].block_table("Aderência média"):
            lid = local_id(r["Local"])
            c.cmp(pid, "Resumo", lid, "aderência Lua", r["Lua"], ad[(lid, "lua")]["aderencia"])
            c.cmp(pid, "Resumo", lid, "aderência Marte", r["Marte"], ad[(lid, "marte")]["aderencia"])
            c.cmp(pid, "Resumo", lid, "o modelo indica", r["O modelo indica"], _rotulo_alvo(ad[(lid, "lua")]["modelo_indica"]))
            c.cmp(pid, "Resumo", lid, "bate?", r["Bate?"], {True: "Sim", False: "Não", None: None}[ad[(lid, "lua")]["bate"]])

    # 5. Rede: Notas, Melhor por utilidade, Por local, Resumo (cobertura)
    rede = books["rede"]
    for _, r in rede["Notas"].table():
        a = alvo_id(r["Alvo"])
        for nome in config_nomes_rede(rede):
            lid = local_id(nome)
            c.cmp("rede", "Notas", f"{r['ID']} | {a} | {lid}", "nota", r[nome], nu[(lid, r["ID"], a)])
    nome_rede = {local_id(n): n for n in config_nomes_rede(rede)}
    melhor = {(m["utilidade_id"], m["alvo_id"]): m for m in res["melhor_por_utilidade"]}
    for _, r in rede["Melhor por utilidade"].table():
        m = melhor[(r["ID"], alvo_id(r["Alvo"]))]
        k = f"{r['ID']} | {m['alvo_id']}"
        c.cmp("rede", "Melhor por utilidade", k, "melhor nota", r["Melhor nota"], m["melhor_nota"])
        c.cmp("rede", "Melhor por utilidade", k, "melhor local", r["Melhor local (primeiro)"], nome_rede.get(m["melhor_local_id"]))
        c.cmp("rede", "Melhor por utilidade", k, "empatados", r["Locais com a melhor nota"],
              ", ".join(nome_rede[x] for x in m["empatados"]) or None)
        c.cmp("rede", "Melhor por utilidade", k, "nº empatados", r["Nº de locais empatados"],
              m["n_empatados"] if m["melhor_nota"] is not None else None)
        c.cmp("rede", "Melhor por utilidade", k, "segunda nota", r["Segunda nota"], m["segunda_nota"])
        c.cmp("rede", "Melhor por utilidade", k, "local da segunda nota", r["Local com a segunda nota"],
              nome_rede.get(m["segundo_local_id"]))
        c.cmp("rede", "Melhor por utilidade", k, "situação", r["Situação"], m["situacao"])
    for _, r in rede["Por local"].table():
        lid = local_id(r["Local"])
        c.cmp("rede", "Por local", lid, "aderência Lua", r["Aderência Lua"], ad[(lid, "lua")]["aderencia"])
        c.cmp("rede", "Por local", lid, "aderência Marte", r["Aderência Marte"], ad[(lid, "marte")]["aderencia"])
        c.cmp("rede", "Por local", lid, "o modelo indica", r["O modelo indica"], _rotulo_alvo(ad[(lid, "lua")]["modelo_indica"]))
        c.cmp("rede", "Por local", lid, "melhor em (nota ≥ 2)", r["Utilidades em que é o melhor (nota ≥ 2)"],
              ad[(lid, "lua")]["n_melhor_em"] + ad[(lid, "marte")]["n_melhor_em"])
    cob = {x["alvo_id"]: x for x in res["cobertura"]}
    # Prefixo do rótulo do indicador na planilha -> campo recalculado
    campos = {"utilidades": "avaliadas", "cobertas": "cobertas", "lacunas": "lacunas", "ainda a medir": "a_medir"}
    for _, r in rede["Resumo"].block_table("Cobertura da rede"):
        campo = next(v for k, v in campos.items() if norm(r["Indicador"]).startswith(k))
        for a in config.ALVOS:
            c.cmp("rede", "Resumo", f"Cobertura | {a}", campo, r[_rotulo_alvo(a)], cob[a][campo])

    # 6. Validação da base (literatura × modelo)
    sh = books["base-v1-1"]["Validação"]
    casos = {v["linha_excel"]: v for v in res["validacao"]}
    for linha, r in sh.table():
        v = casos[linha]
        c.cmp("base-v1-1", "Validação", v["id"], "nota do modelo", r["Nota do modelo"], v["nota_modelo"])
        c.cmp("base-v1-1", "Validação", v["id"], "bate?", r["Bate?"], {True: "Sim", False: "Não", None: "A medir"}[v["bate"]])
    total = sh.cell(sh.find_row("Casos que batem"), 2)
    ok = sum(v["bate"] is True for v in res["validacao"])
    c.cmp("base-v1-1", "Validação", "Casos que batem", "total", total, f"{ok} de {len(res['validacao'])}")

    return c.resumo()


def _eh_local(cabecalho, lid):
    try:
        return local_id(cabecalho) == lid
    except KeyError:
        return False


def config_nomes_rede(rede):
    return rede["Notas"].header()[4:]
