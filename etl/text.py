"""Funções puras de texto: normalização, slugs, aliases, números em pt-BR e códigos de fonte."""
import re
import unicodedata

from . import config


def norm(s):
    """Normaliza um rótulo para comparação: minúsculas, traços unificados, espaços colapsados."""
    s = str(s).replace("–", "–").replace("—", "–")
    return re.sub(r"\s+", " ", s).strip().casefold()


def slugify(s):
    """'Temperatura média (0–3)' -> 'temperatura-media-0-3' (ASCII, minúsculas, hífens)."""
    s = re.sub(r"[–—−]", "-", str(s))
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def _alias_index(table, key=lambda v: v):
    idx = {}
    for id_, v in table.items():
        for alias in key(v):
            idx[norm(alias)] = id_
    return idx


_LOCAL_IDX = _alias_index(config.LOCAIS)
_ALVO_IDX = _alias_index(config.ALVOS, key=lambda v: v["aliases"])


def local_id(nome):
    """Resolve um nome de local (em qualquer variação das abas) para o id estável. Falha se desconhecido."""
    s = norm(nome)
    s = re.sub(r"^nota ", "", s)
    s = re.sub(r" \(valor\)$", "", s)
    try:
        return _LOCAL_IDX[s]
    except KeyError:
        raise KeyError(f"Local desconhecido: {nome!r}. Adicione o alias em etl/config.py (LOCAIS).") from None


def alvo_id(nome):
    try:
        return _ALVO_IDX[norm(nome)]
    except KeyError:
        raise KeyError(f"Alvo desconhecido: {nome!r}. Adicione o alias em etl/config.py (ALVOS).") from None


def alvos_de(texto):
    """'Lua e Marte' -> ['lua', 'marte']; 'Marte' -> ['marte']."""
    partes = re.split(r"\s+e\s+|,|;", str(texto))
    return sorted({alvo_id(p) for p in partes if p.strip()}, key=list(config.ALVOS).index)


def sem_valor(v):
    """True para vazio e textos do tipo 'A extrair', 'A medir', '—'."""
    if v is None:
        return True
    if isinstance(v, str):
        s = norm(v)
        return s in config.TEXTOS_SEM_VALOR or any(s.startswith(t) for t in config.TEXTOS_SEM_VALOR if t)
    return False


# ---------- números em texto (pt-BR) ----------

_NUM = r"[−-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
_RE_VALOR = re.compile(
    rf"^(?P<q>[≈~<>≤≥])?\s*(?P<a>{_NUM})(?:\s*(?:[–—]|\sa\s)\s*(?P<b>{_NUM}))?"
    r"(?P<resto>.*)$"
)


def to_float(s):
    """'−1.010,5' -> -1010.5. Ponto = milhar, vírgula = decimal, '−' unicode = menos."""
    s = s.replace("−", "-").replace(".", "").replace(",", ".")
    return float(s)


def parse_valor_texto(texto):
    """Extrai números de um texto livre do Catálogo sem forçar o que não é numérico.

    Aceita só textos que começam com o número (ou faixa) e, no máximo, terminam com um parêntese de
    comentário: '≈900 (alt. ~1.000 m)' -> 900; '−5,7 a 37,9' -> faixa; '0,64–0,67 (RAD)' -> faixa.
    Textos como '≈38 (Badwater) a 42 (Furnace Creek)' ou 'Média ≈0,03; pico ≈0,6' ficam sem número.
    """
    out = {"valor_texto": texto, "valor_num": None, "valor_min": None, "valor_max": None, "qualificador": None}
    if texto is None:
        return out
    if isinstance(texto, (int, float)):
        out.update(valor_texto=str(texto), valor_num=float(texto))
        return out
    m = _RE_VALOR.match(str(texto).strip())
    if not m:
        return out
    resto = m.group("resto").strip()
    if resto and not re.fullmatch(r"\([^()]*(?:\([^()]*\)[^()]*)*\)?", resto):
        return out
    a = to_float(m.group("a"))
    out["qualificador"] = m.group("q")
    if m.group("b"):
        b = to_float(m.group("b"))
        out["valor_min"], out["valor_max"] = min(a, b), max(a, b)
    else:
        out["valor_num"] = a
    return out


# ---------- códigos de fonte ----------

_RE_FONTE = re.compile(r"\b([FGHR]\d{1,3})\b")


def fonte_ids(texto):
    """'F1, F2, F9' -> ['F1','F2','F9']; 'Aba Locais' -> []."""
    if texto is None:
        return []
    vistos = []
    for f in _RE_FONTE.findall(str(texto)):
        if f not in vistos:
            vistos.append(f)
    return vistos


def fonte_ids_do_local(texto, nomes_do_local):
    """Fontes que valem para um local numa célula como 'G1; McMurdo: G12; Mauna Kea: G1 corrigido'.

    Regra: se houver um trecho 'Local: ...' para este local, valem só as fontes desse trecho; senão,
    valem os trechos sem prefixo de local.
    """
    if texto is None:
        return []
    nomes = {norm(n) for n in nomes_do_local}
    especificos, gerais = [], []
    for trecho in re.split(r";", str(texto)):
        m = re.match(r"\s*([^:]+):(.*)$", trecho)
        if m and norm(m.group(1)) in nomes:
            especificos.append(m.group(2))
        elif m and fonte_ids(m.group(1)) == [] and _parece_local(m.group(1)):
            continue  # trecho de outro local
        else:
            gerais.append(trecho)
    return fonte_ids(" ".join(especificos if especificos else gerais))


def _parece_local(s):
    try:
        local_id(s)
        return True
    except KeyError:
        return False
