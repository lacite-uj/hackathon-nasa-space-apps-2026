"""Scoring: o modelo de aderência, reescrito em Python a partir das fórmulas do Excel.

Regras (ver o Resumo da base v1.1 e docs/instrucoes-desenvolvimento.md):

1. Nota da variável (0–3): o valor do local cai numa faixa definida pelo critério.
     sentido "maior": valor >= n3 -> 3; >= n2 -> 2; >= n1 -> 1; senão 0
     sentido "menor": valor <= n3 -> 3; <= n2 -> 2; <= n1 -> 1; senão 0
   Valor vazio ou faixas vazias -> None (a medir). Vazio NUNCA vira zero.
2. Nota da utilidade (local × utilidade × alvo) = média das notas de variável não vazias.
3. Nota da categoria = média das notas de utilidade não vazias da categoria.
4. Aderência do local ao alvo = média das notas de utilidade não vazias do alvo, sem a categoria
   "Limitações universais".
5. Rede: melhor nota por utilidade × alvo, empatados, segunda nota e situação
   (A medir / Coberta se melhor >= 2 / Lacuna).

Todos os pesos valem 1 por enquanto. As médias já aceitam pesos (`media(..., pesos)`) para quando o
modelo tiver pesos, mas nenhum peso diferente de 1 é aplicado.
"""
from collections import defaultdict

from . import config

COBERTA_MIN = 2.0


def nota_variavel(valor, sentido, faixas):
    """Nota 0–3 de um valor segundo as faixas do critério. None = a medir."""
    n3, n2, n1 = faixas["nota_3"], faixas["nota_2"], faixas["nota_1"]
    if valor is None or n3 is None:
        return None
    if n2 is None or n1 is None:
        raise ValueError(f"faixas incompletas: {faixas}")
    if sentido == "maior":
        return 3 if valor >= n3 else 2 if valor >= n2 else 1 if valor >= n1 else 0
    if sentido == "menor":
        return 3 if valor <= n3 else 2 if valor <= n2 else 1 if valor <= n1 else 0
    raise ValueError(f"sentido inválido: {sentido!r}")


def media(valores, pesos=None):
    """Média ponderada ignorando None. Sem nenhum valor -> None. Pesos ausentes valem 1."""
    pares = [(v, 1.0 if pesos is None else pesos[i]) for i, v in enumerate(valores) if v is not None]
    total = sum(p for _, p in pares)
    if not pares or total == 0:
        return None
    return sum(v * p for v, p in pares) / total


def _pares_utilidade_alvo(criterios):
    """(utilidade, alvo) na ordem das linhas de critério, sem repetição. Igual para todos os conjuntos."""
    por_conj = defaultdict(list)
    for c in criterios:
        par = (c["utilidade_id"], c["alvo_id"])
        if par not in por_conj[c["conjunto_id"]]:
            por_conj[c["conjunto_id"]].append(par)
    listas = list(por_conj.values())
    if any(l != listas[0] for l in listas):
        raise ValueError("Os conjuntos de critérios não cobrem as mesmas utilidades × alvos")
    return listas[0]


def compute(model, pesos_variavel=None):
    """Recalcula todas as notas a partir de critérios + valores. Devolve tabelas em formato longo."""
    locais = model["locais"]
    utils = {u["id"]: u for u in model["utilidades"]}
    cats = model["categorias"]
    valores = {(v["local_id"], v["variavel_id"]): v["valor"] for v in model["valores"]}
    crit_por = defaultdict(list)
    for c in model["criterios"]:
        crit_por[(c["conjunto_id"], c["utilidade_id"], c["alvo_id"])].append(c)
    pares = _pares_utilidade_alvo(model["criterios"])
    leituras = model.get("_leituras", {})

    notas_var, notas_util = [], []
    nu = {}  # (local, utilidade, alvo) -> nota
    for l in locais:
        for (u, a) in pares:
            crits = crit_por[(l["conjunto_criterios"], u, a)]
            notas = []
            for c in crits:
                v = valores.get((l["id"], c["variavel_id"]))
                n = nota_variavel(v, c["sentido"], c["faixas"])
                notas.append(n)
                notas_var.append({
                    "local_id": l["id"], "criterio_id": c["id"], "conjunto_id": c["conjunto_id"],
                    "utilidade_id": u, "alvo_id": a, "variavel_id": c["variavel_id"],
                    "valor": v, "nota": n,
                    "status": "avaliada" if n is not None else ("sem_faixas" if c["faixas"]["nota_3"] is None else "a_medir"),
                })
            pesos = [(pesos_variavel or {}).get(c["variavel_id"], c["peso"]) for c in crits]
            nota = media(notas, pesos)
            nu[(l["id"], u, a)] = nota
            notas_util.append({
                "local_id": l["id"], "utilidade_id": u, "alvo_id": a, "categoria_id": utils[u]["categoria_id"],
                "nota": nota, "status": "avaliada" if nota is not None else "a_medir",
                "n_variaveis": len(crits), "n_variaveis_avaliadas": sum(n is not None for n in notas),
                "leitura": leituras.get((u, a)) if l["lote"] == "base-v1-1" else None,
            })

    # Categorias
    notas_cat = []
    for l in locais:
        for c in cats:
            for a in config.ALVOS:
                us = [u for (u, al) in pares if al == a and utils[u]["categoria_id"] == c["id"]]
                if not us:
                    continue
                ns = [nu[(l["id"], u, a)] for u in us]
                notas_cat.append({
                    "local_id": l["id"], "categoria_id": c["id"], "alvo_id": a, "nota": media(ns),
                    "n_utilidades": len(us), "n_avaliadas_local": sum(n is not None for n in ns),
                    "n_avaliadas_rede": sum(any(nu[(x["id"], u, a)] is not None for x in locais) for u in us),
                })

    # Melhor por utilidade (rede, na ordem dos locais)
    melhor = []
    for (u, a) in pares:
        notas = [(l["id"], nu[(l["id"], u, a)]) for l in locais]
        validas = [(lid, n) for lid, n in notas if n is not None]
        if not validas:
            melhor.append({"utilidade_id": u, "alvo_id": a, "categoria_id": utils[u]["categoria_id"],
                           "melhor_nota": None, "melhor_local_id": None, "empatados": [], "n_empatados": 0,
                           "segunda_nota": None, "segundo_local_id": None, "situacao": "A medir"})
            continue
        top = max(n for _, n in validas)
        empatados = [lid for lid, n in validas if n == top]
        abaixo = [(lid, n) for lid, n in validas if n < top]
        seg = max((n for _, n in abaixo), default=None)
        melhor.append({
            "utilidade_id": u, "alvo_id": a, "categoria_id": utils[u]["categoria_id"],
            "melhor_nota": top, "melhor_local_id": empatados[0], "empatados": empatados,
            "n_empatados": len(empatados), "segunda_nota": seg,
            "segundo_local_id": next((lid for lid, n in abaixo if n == seg), None),
            "situacao": "Coberta" if top >= COBERTA_MIN else "Lacuna",
        })

    # Aderência e resumo por local
    aderencia = []
    for l in locais:
        por_alvo = {}
        for a in config.ALVOS:
            us = [u for (u, al) in pares if al == a]
            entra = [nu[(l["id"], u, a)] for u in us if utils[u]["categoria_id"] not in config.CATEGORIAS_FORA_DA_ADERENCIA]
            por_alvo[a] = {
                "local_id": l["id"], "alvo_id": a, "aderencia": media(entra),
                "n_utilidades": len(us),
                "n_consideradas": sum(n is not None for n in entra),
                "n_fortes": sum(nu[(l["id"], u, a)] == 3 for u in us),
                "n_a_medir": sum(nu[(l["id"], u, a)] is None for u in us),
                "n_melhor_em": sum(1 for m in melhor if m["alvo_id"] == a and l["id"] in m["empatados"]
                                   and m["melhor_nota"] >= COBERTA_MIN),
            }
        lua, marte = por_alvo["lua"]["aderencia"], por_alvo["marte"]["aderencia"]
        indica = None if lua is None or marte is None else "lua" if lua > marte else "marte" if marte > lua else "empate"
        for a, row in por_alvo.items():
            row["modelo_indica"] = indica
            row["bate"] = None if indica is None else indica in l["listado_como"]
            row["rank"] = None
            row["rank_empatado"] = False
            aderencia.append(row)
    for a in config.ALVOS:
        rows = sorted((r for r in aderencia if r["alvo_id"] == a and r["aderencia"] is not None),
                      key=lambda r: -r["aderencia"])
        for i, r in enumerate(rows, 1):
            r["rank"] = i
            # O rank é posição única (o sort é estável: empates ficam na ordem da rede). Quem divide a
            # mesma aderência com outro local fica marcado, para a interface não sugerir uma ordem que não existe.
            r["rank_empatado"] = any(o is not r and abs(o["aderencia"] - r["aderencia"]) <= config.TOLERANCIA_EMPATE
                                     for o in rows)

    cobertura = []
    for a in config.ALVOS:
        ms = [m for m in melhor if m["alvo_id"] == a]
        cobertura.append({
            "alvo_id": a, "total": len(ms),
            "avaliadas": sum(m["situacao"] != "A medir" for m in ms),
            "cobertas": sum(m["situacao"] == "Coberta" for m in ms),
            "lacunas": sum(m["situacao"] == "Lacuna" for m in ms),
            "a_medir": sum(m["situacao"] == "A medir" for m in ms),
        })

    ad = {(r["local_id"], r["alvo_id"]): r["aderencia"] for r in aderencia}
    validacao = []
    for v in model["validacao_casos"]:
        if v["utilidade_id"]:
            nota = nu[(v["local_id"], v["utilidade_id"], v["alvos"][0])]
            regra = "nota >= 2" if v["expectativa"].startswith("Alta") else "nota <= 1"
            bate = None if nota is None else (nota >= 2 if regra == "nota >= 2" else nota <= 1)
        else:  # caso agregado "Marte × Lua": diferença entre as aderências
            a1, a2 = v["alvos"]
            nota = ad[(v["local_id"], a1)] - ad[(v["local_id"], a2)]
            regra = f"aderencia_{a1} - aderencia_{a2} > 0"
            bate = nota > 0
        validacao.append({**v, "regra": regra, "nota_modelo": nota, "bate": bate})

    return {
        "notas_variavel": notas_var,
        "notas_utilidade": notas_util,
        "notas_categoria": notas_cat,
        "aderencia": aderencia,
        "melhor_por_utilidade": melhor,
        "cobertura": cobertura,
        "validacao": validacao,
    }
