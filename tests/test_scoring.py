"""Testes unitários das regras do modelo (não precisam das planilhas)."""
import pytest

from etl import scoring
from etl.text import fonte_ids, fonte_ids_do_local, parse_valor_texto, slugify

F = {"nota_3": -150, "nota_2": -80, "nota_1": -20}       # sentido "menor" (U01 Lua, temperatura média)
G = {"nota_3": 50, "nota_2": 25, "nota_1": 10}           # sentido "maior" (U15)


# ---------- nota da variável (0–3) ----------

@pytest.mark.parametrize("valor,esperado", [
    (-200, 3), (-150, 3),        # igual ao limite conta para a nota maior
    (-149.9, 2), (-80, 2),
    (-79.9, 1), (-20, 1),
    (-19.9, 0), (16.5, 0),
])
def test_nota_menor(valor, esperado):
    assert scoring.nota_variavel(valor, "menor", F) == esperado


@pytest.mark.parametrize("valor,esperado", [(50, 3), (49.99, 2), (25, 2), (10, 1), (9.99, 0), (0.5, 0)])
def test_nota_maior(valor, esperado):
    assert scoring.nota_variavel(valor, "maior", G) == esperado


def test_valor_vazio_e_a_medir_nao_zero():
    assert scoring.nota_variavel(None, "maior", G) is None


def test_zero_e_valor_valido():
    assert scoring.nota_variavel(0, "menor", {"nota_3": 1, "nota_2": 10, "nota_1": 50}) == 3


def test_faixas_vazias_e_a_medir():
    assert scoring.nota_variavel(30, "maior", {"nota_3": None, "nota_2": None, "nota_1": None}) is None


def test_sentido_invalido():
    with pytest.raises(ValueError):
        scoring.nota_variavel(1, "igual", G)


# ---------- médias ----------

def test_media_ignora_vazios():
    assert scoring.media([3, None, 1]) == 2
    assert scoring.media([None, None]) is None
    assert scoring.media([]) is None


def test_media_preparada_para_pesos():
    assert scoring.media([3, 0], [1, 1]) == 1.5
    assert scoring.media([3, 0], [2, 1]) == 2
    assert scoring.media([3, None, 0], [2, 5, 1]) == 2  # peso de valor vazio não conta


# ---------- modelo mínimo: exclusão de Limitações universais ----------

def _modelo_minimo(valor_u15):
    crit = lambda u, a, v, f: {"id": f"c.{u}.{a}.{v}", "conjunto_id": "c", "utilidade_id": u, "alvo_id": a,
                               "variavel_id": v, "sentido": "maior", "faixas": f, "peso": 1.0}
    f = {"nota_3": 3, "nota_2": 2, "nota_1": 1}
    return {
        "locais": [{"id": "x", "conjunto_criterios": "c", "lote": "lote-2", "listado_como": ["marte"]}],
        "utilidades": [{"id": "U01", "categoria_id": "engenharia", "alvos": ["lua", "marte"]},
                       {"id": "U15", "categoria_id": "limitacoes-universais", "alvos": ["lua", "marte"]}],
        "categorias": [{"id": "engenharia"}, {"id": "limitacoes-universais"}],
        "criterios": [crit("U01", "lua", "a", f), crit("U01", "marte", "b", f),
                      crit("U15", "lua", "r", f), crit("U15", "marte", "r", f)],
        "valores": [{"local_id": "x", "variavel_id": "a", "valor": 1}, {"local_id": "x", "variavel_id": "b", "valor": 3},
                    {"local_id": "x", "variavel_id": "r", "valor": valor_u15}],
        "validacao_casos": [],
    }


def test_aderencia_exclui_limitacoes_universais():
    for u15 in (0, 3):  # a nota do U15 não muda a aderência
        res = scoring.compute(_modelo_minimo(u15))
        ad = {r["alvo_id"]: r for r in res["aderencia"]}
        assert ad["lua"]["aderencia"] == 1 and ad["marte"]["aderencia"] == 3
        assert ad["marte"]["modelo_indica"] == "marte" and ad["marte"]["bate"] is True
    # mas entra na contagem de notas 3 e na nota da categoria
    res = scoring.compute(_modelo_minimo(3))
    assert {r["alvo_id"]: r["n_fortes"] for r in res["aderencia"]} == {"lua": 1, "marte": 2}


def test_utilidade_sem_valor_fica_a_medir():
    res = scoring.compute(_modelo_minimo(None))
    u15 = [n for n in res["notas_utilidade"] if n["utilidade_id"] == "U15"]
    assert all(n["nota"] is None and n["status"] == "a_medir" for n in u15)
    assert {m["situacao"] for m in res["melhor_por_utilidade"] if m["utilidade_id"] == "U15"} == {"A medir"}


# ---------- parsing de texto ----------

@pytest.mark.parametrize("texto,campo,esperado", [
    ("9,81", "valor_num", 9.81),
    ("≈900 (alt. ~1.000 m)", "valor_num", 900),
    ("≈1.010 (perto do nível do mar)", "valor_num", 1010),
    ("−16", "valor_num", -16),
    ("7,18 (718 Pa, MEDA)", "valor_num", 7.18),
    ("−5,7 a 37,9", "valor_min", -5.7),
    ("−5,7 a 37,9", "valor_max", 37.9),
    ("0,64–0,67 (RAD, cratera Gale)", "valor_max", 0.67),
    ("−83 a −23", "valor_min", -83),
])
def test_parse_valor_texto(texto, campo, esperado):
    assert parse_valor_texto(texto)[campo] == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["A extrair", "Média ≈0,03; pico ≈0,6", "≈38 (Badwater) a 42 (Furnace Creek)",
                                   "PSR de Cabeus: ≈−236 (37 K)", "Ausente"])
def test_parse_nao_forca_numero(texto):
    p = parse_valor_texto(texto)
    assert p["valor_num"] is None and p["valor_min"] is None and p["valor_texto"] == texto


def test_fontes():
    assert fonte_ids("F1, F2, F9") == ["F1", "F2", "F9"]
    assert fonte_ids("Aba Locais") == []
    cel = "G1; McMurdo: G12; Mauna Kea: G1 corrigido"
    assert fonte_ids_do_local(cel, ["McMurdo"]) == ["G12"]
    assert fonte_ids_do_local(cel, ["Mauna Kea"]) == ["G1"]
    assert fonte_ids_do_local(cel, ["Askja"]) == ["G1"]


def test_slug():
    assert slugify("Nível de UV (0–3)") == "nivel-de-uv-0-3"
    assert slugify("Lençóis Maranhenses") == "lencois-maranhenses"
