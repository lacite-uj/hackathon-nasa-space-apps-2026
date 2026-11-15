"""Testes de regressão com as planilhas reais (pulados se data/raw/ não tiver os arquivos)."""
import json

import pytest

import copy
import re

from etl import config, curadoria, extract, load, scoring, site, transform, validate

pytestmark = pytest.mark.skipif(
    not all((config.RAW_DIR / p["arquivo"]).exists() for p in config.PLANILHAS.values()),
    reason="planilhas ausentes em data/raw/",
)

# Seção 6 do prompt do ETL (aba "Por local" da rede): Lua, Marte, "melhor em (nota ≥ 2)".
ESPERADO = {
    "atacama": (0.4091, 0.9643, 4), "haughton": (1.1818, 1.5385, 8), "vale-da-morte": (0.9091, 1.1250, 4),
    "cinder-lake": (0.6250, 0.7143, 1), "meteor-crater": (0.6250, 0.8214, 3), "holuhraun": (0.6250, 0.8571, 3),
    "mauna-kea": (0.5000, 0.8214, 1), "mcmurdo": (0.7917, 1.0714, 6), "rio-tinto": (0.3333, 0.8214, 2),
    "askja": (0.5833, 0.8571, 1), "vargeao": (0.6250, 0.9643, 3), "araguainha": (0.7917, 1.0357, 6),
    "lencois-maranhenses": (0.2917, 0.5357, 2), "toca-da-boa-vista": (0.6250, 0.7143, 5),
}


@pytest.fixture(scope="module")
def etl():
    books, arquivos = extract.load()
    model = transform.build(books, arquivos)
    res = scoring.compute(model)
    return books, model, res


@pytest.fixture(scope="module")
def curado(etl):
    """Modelo depois da curadoria das fontes (é o que vai para o site)."""
    books, model, _ = etl
    m = copy.deepcopy(model)
    rel = curadoria.aplicar(m)
    return books, m, scoring.compute(m), rel


def test_tabela_da_secao_6(etl):
    _, _, res = etl
    ad = {(a["local_id"], a["alvo_id"]): a for a in res["aderencia"]}
    for lid, (lua, marte, melhor) in ESPERADO.items():
        assert ad[(lid, "lua")]["aderencia"] == pytest.approx(lua, abs=5e-5), lid
        assert ad[(lid, "marte")]["aderencia"] == pytest.approx(marte, abs=5e-5), lid
        assert ad[(lid, "lua")]["n_melhor_em"] + ad[(lid, "marte")]["n_melhor_em"] == melhor, lid


def test_cobertura_da_rede(etl):
    _, _, res = etl
    cob = {c["alvo_id"]: (c["avaliadas"], c["cobertas"], c["lacunas"], c["a_medir"]) for c in res["cobertura"]}
    assert cob == {"lua": (13, 8, 5, 2), "marte": (15, 13, 2, 2)}


def test_validacao_literatura_9_de_9(etl):
    _, _, res = etl
    assert [v["bate"] for v in res["validacao"]] == [True] * 9


def test_recalculado_igual_ao_cache_do_excel(etl):
    books, model, res = etl
    rel = validate.run(books, model, res)
    assert rel["comparadas"] > 2000
    assert rel["divergencias"] == 0, rel["lista_divergencias"][:5]


def test_validador_detecta_mudanca(etl):
    books, model, _ = etl
    m = json.loads(json.dumps({k: v for k, v in model.items() if not k.startswith("_")}))
    m["_leituras"], m["_crit_linhas"] = model["_leituras"], model["_crit_linhas"]
    for v in m["valores"]:
        if v["local_id"] == "haughton" and v["variavel_id"] == "temperatura-media":
            v["valor"] = -50
    assert validate.run(books, m, scoring.compute(m))["divergencias"] > 0


def test_u03_u09_a_medir_em_todos(etl):
    _, _, res = etl
    for n in res["notas_utilidade"]:
        if n["utilidade_id"] in ("U03", "U09"):
            assert n["nota"] is None and n["status"] == "a_medir"


def test_pegadinhas(etl):
    _, model, res = etl
    locais = {l["id"]: l for l in model["locais"]}
    vdm = locais["vale-da-morte"]
    assert (vdm["lat"], vdm["lon"], vdm["coordenada_aproximada"]) == (36.25, -116.75, True)
    # U15 da base dividido em duas variáveis canônicas, as mesmas dos lotes
    vals = {(v["local_id"], v["variavel_id"]): v["valor"] for v in model["valores"]}
    assert vals[("atacama", "dose-radiacao-pct-lua")] == 0.5 and vals[("atacama", "dose-radiacao-pct-marte")] == 1
    assert vals[("mcmurdo", "dose-radiacao-pct-lua")] == 0.5
    # UV: variáveis diferentes por conjunto
    crit = {(c["conjunto_id"], c["utilidade_id"], c["alvo_id"]): c for c in model["criterios"]}
    assert crit[("base-v1-1", "U04", "lua")]["variavel_id"] == "nivel-de-uv-0-3"
    assert crit[("lotes-v1-1", "U04", "lua")]["variavel_id"] == "indice-uv-medio-anual"
    assert crit[("lotes-v1-1", "U04", "lua")]["faixas"] == {"nota_3": 2, "nota_2": 1.5, "nota_1": 1}
    # Vazio é null, nunca zero
    assert all(v["valor"] is None for v in model["valores"] if v["status"] == "a_medir")
    # Araguainha U19: só a origem por impacto tem valor
    u19 = next(n for n in res["notas_utilidade"]
               if (n["local_id"], n["utilidade_id"]) == ("araguainha", "U19"))
    assert (u19["nota"], u19["n_variaveis_avaliadas"], u19["n_variaveis"]) == (3, 1, 2)
    # Fonte específica por local
    t = next(v for v in model["valores"] if (v["local_id"], v["variavel_id"]) == ("mcmurdo", "temperatura-media"))
    assert t["fonte_ids"] == ["G12"]
    assert {v["id"]: v["unidade"] for v in model["variaveis"]}["rugosidade-do-terreno"] == "m"


def test_site_json_valido_e_ligado_aos_dados(curado):
    _, model, res, _ = curado
    s = site.build(model, res, "2026-11-15T00:00:00Z")
    load.validar_site(s)
    assert {t["id"] for t in s["targets"]} == {"lua", "marte"}
    assert {t["body"] for t in s["targets"]} == {"moon", "mars"}
    assert [a["id"] for a in s["analogs"]] == list(config.LOCAIS)
    assert len(s["links"]) == 28
    hau = next(l for l in s["links"] if (l["analog"], l["target"]) == ("haughton", "marte"))
    assert hau["adherence"] == pytest.approx(1.5385, abs=5e-5)
    assert hau["score"] == pytest.approx(1.5385 / 3, abs=5e-5)
    assert hau["rank"] == 1 and hau["limits"] and hau["sources"]
    assert all(l["limits"] for l in s["links"])
    # rank_tied marca exatamente os links que dividem a aderência com outro local do mesmo alvo.
    for l in s["links"]:
        iguais = [o for o in s["links"] if o["target"] == l["target"] and o["adherence"] == l["adherence"]]
        assert l["rank_tied"] == (len(iguais) > 1), (l["analog"], l["target"])
    assert hau["rank_tied"] is False
    empatados_lua = {l["analog"] for l in s["links"] if l["target"] == "lua" and l["rank_tied"]}
    assert {"cinder-lake", "meteor-crater", "holuhraun", "vargeao", "toca-da-boa-vista"} <= empatados_lua


def test_site_imagens_dos_locais(curado):
    _, model, res, _ = curado
    s = site.build(model, res, "2026-11-15T00:00:00Z")
    assert set(config.IMAGENS) == set(config.LOCAIS)
    for a in s["analogs"]:
        img = a["image"]
        assert img["src"] == f"images/analogs/{a['id']}.jpg"
        assert (config.ROOT / "web" / img["src"]).is_file()
        assert img["credit"]["author"] and img["credit"]["source_url"].startswith("https://commons.wikimedia.org/")
        # licença CC precisa de link; domínio público não tem
        assert (img["credit"]["license_url"] is None) == (img["credit"]["license"] == "Domínio público")
    assert next(a for a in s["analogs"] if a["id"] == "vargeao")["image"]["kind"] == "satelite"


def test_site_falha_sem_arquivo_de_imagem(curado, monkeypatch, tmp_path):
    _, model, res, _ = curado
    monkeypatch.setattr(config, "IMAGENS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        site.build(model, res, "2026-11-15T00:00:00Z")


def test_site_niveis_pontos_e_evidencias(curado):
    _, model, res, _ = curado
    s = site.build(model, res, "2026-11-15T00:00:00Z")
    load.validar_site(s)
    for l in s["links"]:
        assert l["level"] == config.nivel(l["adherence"])
        for d in l["dimensions"].values():
            assert d["level"] == config.nivel(d["adherence"])
        us = {u["id"]: u for u in l["utilities"]}
        for u in us.values():
            assert u["level"] == config.nivel(u["adherence"])
            assert u["meaning"]["purpose"] and u["evidence"], (l["analog"], l["target"], u["id"])
            for e in u["evidence"]:
                assert all(fid in s["source_index"] for fid in e["sources"])
        # Pontos fortes e fracos apontam para utilidades do link, com o mesmo nível e o lado certo do limiar.
        for p in l["strengths"]:
            if p["kind"] == "utility":
                assert us[p["id"]]["adherence"] >= config.LIMIAR_FORTE and p["level"] == "high"
        for p in l["limits"]:
            if p["kind"] == "utility":
                assert us[p["id"]]["adherence"] <= config.LIMIAR_FRACO and p["level"] == "low"
    # Nota 1,0 conta como fraca (mesmo limiar da aba Validação), nunca como parcial.
    assert config.nivel(1.0) == "low" and config.nivel(1.5) == "moderate" and config.nivel(2.0) == "high"
    assert config.nivel(None) is None
    hau = next(l for l in s["links"] if (l["analog"], l["target"]) == ("haughton", "marte"))
    u01 = next(u for u in hau["utilities"] if u["id"] == "U01")
    assert u01["meaning"]["condition"] == "noites com solo a −83 °C"
    temp = next(e for e in u01["evidence"] if e["variable"] == "Temperatura média")
    assert temp["value"] == -16.0 and temp["note"] == 1 and temp["sources_scope"] == "catalogo"
    assert temp["dataset_earth"] == "MODIS LST (MOD11)" and temp["dataset_target"] == "MEDA"
    # Narrativas curadas: as 10 do dossiê; os outros locais ficam com null.
    narr = {a["id"] for a in s["analogs"] if a["narrative"]}
    assert narr == set(config.NARRATIVAS)


def test_observacao_so_do_local():
    obs = "McMurdo: solo cimentado por gelo a menos de 1 m. Islândia: geleira vizinha (Dyngjujökull)"
    assert site._observacao_do_local(obs, "mcmurdo") == "solo cimentado por gelo a menos de 1 m."
    assert site._observacao_do_local(obs, "askja") == "geleira vizinha (Dyngjujökull)"
    assert site._observacao_do_local(obs, "rio-tinto") is None
    assert site._observacao_do_local("Igual em toda a superfície da Terra", "vargeao") == \
        "Igual em toda a superfície da Terra"
    misto = "Cinder, Meteor e Askja: treino das equipes Apollo. McMurdo: estação ocupada o ano todo"
    assert site._observacao_do_local(misto, "meteor-crater") == "treino das equipes Apollo."


DESCARTADAS = set(config.FONTES_DESCARTADAS)


def test_curadoria_toda_fonte_tem_classe_ou_foi_descartada(curado):
    _, model, _, rel = curado
    for f in model["fontes"]:
        assert f["classe"] in curadoria.KINDS + ("descartada",), f["id"]
        if f["classe"] == "descartada":
            assert f["descarte"]
    # Wikipedia, imprensa e afins nunca ficam como fonte válida
    for f in model["fontes"]:
        if re.search(r"wikipedia|eurekalert|phys\.org|sciencedaily|space\.com|nbcnews|britannica|pbs\.org",
                     f["link"] or "", re.I):
            assert f["classe"] == "descartada", f["id"]
    assert len(rel["descartadas"]) == len(DESCARTADAS)


def test_curadoria_nao_deixa_fonte_descartada_no_site(curado):
    _, model, res, _ = curado
    s = site.build(model, res, "2026-11-15T00:00:00Z")
    texto = json.dumps({k: v for k, v in s.items() if k != "analogs"}, ensure_ascii=False)
    texto += json.dumps([{k: v for k, v in a.items() if k != "image"} for a in s["analogs"]], ensure_ascii=False)
    assert not (set(re.findall(r"\b[FGHRN]\d+\b", texto)) & DESCARTADAS)
    assert "wikipedia.org" not in texto
    assert all(src["kind"] in curadoria.KINDS for src in s["source_index"].values())
    for l in s["links"]:
        assert all(src["kind"] in curadoria.KINDS for src in l["sources"])
    for d in config.DATASETS_REMOVIDOS:
        assert d not in texto


def test_curadoria_valores_corrigidos_sem_mudar_notas(etl, curado):
    res0 = etl[2]
    _, model, res, rel = curado
    vals = {(v["local_id"], v["variavel_id"]): v for v in model["valores"]}
    for key, cor in config.VALORES_CORRIGIDOS.items():
        assert vals[key]["valor"] == cor["valor"] and vals[key]["fonte_ids"] == cor["fonte_ids"]
    # As correções foram escolhidas de forma conservadora: nenhuma nota muda em relação à planilha.
    assert curadoria.notas_alteradas(res0, res) == []
    assert {(v["local_id"], v["variavel_id"]) for v in rel["valores_corrigidos"]} == set(config.VALORES_CORRIGIDOS)


def test_curadoria_falha_se_valor_ficar_sem_fonte(etl, monkeypatch):
    _, model, _ = etl
    m = copy.deepcopy(model)
    monkeypatch.setattr(config, "VALORES_CORRIGIDOS",
                        {k: v for k, v in config.VALORES_CORRIGIDOS.items() if k[0] != "mcmurdo"})
    with pytest.raises(transform.ModelError, match="sem fonte válida"):
        curadoria.aplicar(m)


def test_curadoria_troca_ids_nos_textos():
    assert curadoria._troca_no_texto("Maior caverna (H10, H11)") == "Maior caverna (H11, N14)"
    assert curadoria._troca_no_texto("estimado (a Lua é ~200× a Terra, F24)") == "estimado (a Lua é ~200× a Terra, F11)"
    assert curadoria._limpa_dataset("Terra: MERRA-2 / ERA5 | Marte: MEDA") == "Terra: MERRA-2 | Marte: MEDA"
    assert curadoria._limpa_dataset("Terra: GPM IMERG / CHIRPS") == "Terra: GPM IMERG"
