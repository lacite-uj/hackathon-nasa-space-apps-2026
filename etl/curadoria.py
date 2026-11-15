"""Curadoria das fontes: aplica etl/config.py › FONTES_* e VALORES_CORRIGIDOS ao modelo já validado.

Ordem no ETL: as planilhas são lidas e conferidas com o cache do Excel como estão; só depois a curadoria
troca as fontes descartadas pelas substitutas, corrige os valores que perderam a fonte e recalcula as notas.
Erros (ModelError) quando:
  - uma fonte citada não tem classe (FONTES_CLASSE) nem está em FONTES_DESCARTADAS;
  - um valor com dado fica sem nenhuma fonte válida depois da troca e não está em VALORES_CORRIGIDOS;
  - sobra qualquer id descartado no modelo.
"""
import re

from . import config
from .transform import ModelError

KINDS = ("nasa", "nasa_mission", "peer_reviewed", "agency", "team")


def _troca(ids):
    out = []
    for fid in ids or []:
        for novo in (config.FONTES_DESCARTADAS[fid][1] if fid in config.FONTES_DESCARTADAS else [fid]):
            if novo not in out:
                out.append(novo)
    return out


_REF = re.compile(r"\b([FGHRN]\d+)\b")


def _troca_no_texto(texto):
    """'(H10, H11)' -> '(H11, N14)': troca ids citados entre parênteses nos textos das planilhas."""
    if not texto:
        return texto

    def grupo(m):
        ids = _troca(_REF.findall(m.group(1)))
        return f"({', '.join(ids)})" if ids else ""
    texto = re.sub(r"\(((?:[FGHRN]\d+)(?:\s*,\s*[FGHRN]\d+)*)\)", grupo, texto)
    # id solto no meio do texto ("..., F24)"): troca pelas substitutas
    texto = _REF.sub(lambda m: ", ".join(_troca([m.group(1)])) if m.group(1) in config.FONTES_DESCARTADAS
                     else m.group(1), texto)
    return texto.replace(" .", ".").strip()


def _limpa_dataset(texto):
    if not texto:
        return texto
    partes = []
    for parte in texto.split("|"):
        corpo, _, itens = parte.partition(":") if ":" in parte else ("", "", parte)
        sep = [s.strip() for s in re.split(r"\s*[/,]\s*", itens)]
        if not any(r in s for s in sep for r in config.DATASETS_REMOVIDOS):
            partes.append(parte.strip())
            continue
        restantes = [s for s in sep if s and not any(r in s for r in config.DATASETS_REMOVIDOS)]
        if restantes:
            partes.append(f"{corpo.strip()}: {' / '.join(restantes)}" if corpo else " / ".join(restantes))
    return " | ".join(partes) or None


def aplicar(model):
    """Altera o modelo no lugar e devolve o relatório da curadoria."""
    fontes = {f["id"]: f for f in model["fontes"]}
    for fid, (ref, link, fornece, kind) in config.FONTES_NOVAS.items():
        if fid in fontes:
            raise ModelError(f"FONTES_NOVAS: id {fid} já existe nas planilhas")
        fontes[fid] = {"id": fid, "planilha_id": "curadoria", "planilha": "etl/config.py", "referencia": ref,
                       "fornece": fornece, "link": link, "observacao": None}
    for fid, (ref, link) in config.FONTES_LINK.items():
        fontes[fid].update(referencia=ref, link=link or fontes[fid]["link"])

    classes = dict(config.FONTES_CLASSE)
    classes.update({fid: v[3] for fid, v in config.FONTES_NOVAS.items()})
    for fid, f in fontes.items():
        if fid in config.FONTES_DESCARTADAS:
            f["classe"], f["descarte"] = "descartada", config.FONTES_DESCARTADAS[fid][0]
            f["substituida_por"] = config.FONTES_DESCARTADAS[fid][1]
        elif classes.get(fid) in KINDS:
            f["classe"], f["descarte"], f["substituida_por"] = classes[fid], None, []
        else:
            raise ModelError(f"Fonte {fid} ({f['referencia']}) sem classe em FONTES_CLASSE nem em FONTES_DESCARTADAS")
    model["fontes"] = sorted(fontes.values(), key=lambda f: ("FGHRN".index(f["id"][0]), int(f["id"][1:])))

    for l in model["locais"]:
        l["fonte_ids"] = _troca(l["fonte_ids"])
        for k in ("justificativa", "por_que_recorte", "recorte", "obs_dados"):
            l[k] = _troca_no_texto(l.get(k))
    for c in model["catalogo_referencia"]:
        c["fonte_ids"] = _troca(c["fonte_ids"])
        c["dataset"] = _troca_no_texto(_limpa_dataset(c["dataset"]))
    for v in model["validacao_casos"]:
        v["fonte_ids"] = _troca(v["fonte_ids"])

    corrigidos, sem_fonte = [], []
    for v in model["valores"]:
        antes = list(v["fonte_ids"])
        v["fonte_ids"] = _troca(v["fonte_ids"])
        for velho, novo in config.OBSERVACOES_CORRIGIDAS.items():
            if v["observacao"] and velho in v["observacao"]:
                v["observacao"] = v["observacao"].replace(velho, novo).replace(". .", ".").strip(" .") or None
        key = (v["local_id"], v["variavel_id"])
        for extra in config.FONTES_EXTRAS.get(key, []):
            if extra not in v["fonte_ids"]:
                v["fonte_ids"].append(extra)
        if key in config.VALORES_CORRIGIDOS:
            cor = config.VALORES_CORRIGIDOS[key]
            corrigidos.append({"local_id": key[0], "variavel_id": key[1], "valor_planilha": v["valor"],
                               "valor": cor["valor"], "fonte_ids": cor["fonte_ids"], "motivo": cor["motivo"]})
            v.update(valor=cor["valor"], fonte_ids=list(cor["fonte_ids"]),
                     status="a_medir" if cor["valor"] is None else "com_valor",
                     status_texto="a medir" if cor["valor"] is None else None, correcao=cor["motivo"])
        elif v["status"] == "com_valor" and antes and not v["fonte_ids"]:
            sem_fonte.append(key)
    if sem_fonte:
        raise ModelError(f"Valores sem fonte válida depois da curadoria (defina VALORES_CORRIGIDOS): {sem_fonte}")
    faltam = [k for k in config.VALORES_CORRIGIDOS if not any((v["local_id"], v["variavel_id"]) == k
                                                               for v in model["valores"])]
    if faltam:
        raise ModelError(f"VALORES_CORRIGIDOS cita valores que não existem: {faltam}")

    # Nenhum id descartado pode sobrar em lugar nenhum.
    usados = set()
    for coll in ("locais", "catalogo_referencia", "validacao_casos", "valores"):
        for r in model[coll]:
            usados.update(r["fonte_ids"])
    sobra = usados & set(config.FONTES_DESCARTADAS)
    if sobra:
        raise ModelError(f"Fontes descartadas ainda citadas: {sorted(sobra)}")
    desconhecidas = usados - set(fontes)
    if desconhecidas:
        raise ModelError(f"Fontes citadas sem cadastro: {sorted(desconhecidas)}")

    por_classe = {}
    for f in model["fontes"]:
        por_classe[f["classe"]] = por_classe.get(f["classe"], 0) + 1
    return {"por_classe": por_classe, "descartadas": [
        {"id": f["id"], "referencia": f["referencia"], "motivo": f["descarte"], "substituida_por": f["substituida_por"]}
        for f in model["fontes"] if f["classe"] == "descartada"], "valores_corrigidos": corrigidos}


def notas_alteradas(antes, depois):
    """Notas de utilidade e aderências que mudaram por causa da curadoria (antes = planilha)."""
    out = []
    a = {(n["local_id"], n["utilidade_id"], n["alvo_id"]): n["nota"] for n in antes["notas_utilidade"]}
    for n in depois["notas_utilidade"]:
        k = (n["local_id"], n["utilidade_id"], n["alvo_id"])
        if a[k] != n["nota"]:
            out.append({"local_id": k[0], "item": k[1], "alvo_id": k[2], "planilha": a[k], "curadoria": n["nota"]})
    a = {(x["local_id"], x["alvo_id"]): x["aderencia"] for x in antes["aderencia"]}
    for x in depois["aderencia"]:
        k = (x["local_id"], x["alvo_id"])
        if a[k] != x["aderencia"]:
            out.append({"local_id": k[0], "item": "aderência", "alvo_id": k[1], "planilha": a[k],
                        "curadoria": x["aderencia"]})
    return out
