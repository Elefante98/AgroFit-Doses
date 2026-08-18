import json
from pathlib import Path

from validacao import validar_registro

UNIDADES = set(json.loads((Path(__file__).parent.parent / "unidades.json").read_text()))

PARES_UVA = [
    {"cultura_norm": "uva", "praga_cientifico_norm": "uncinula necator",
     "praga_comum_norm": "oidio", "praga_nome_cientifico": "Uncinula necator"},
    {"cultura_norm": "uva", "praga_cientifico_norm": "phakopsora euvitis",
     "praga_comum_norm": "ferrugem-da-videira", "praga_nome_cientifico": "Phakopsora euvitis"},
]


def registro_base(**extra):
    r = {"cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
         "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
         "fonte_pagina": 4, "fonte_trecho": "UVA | Oídio | 30"}
    r.update(extra)
    return r


def test_registro_valido():
    status, _ = validar_registro(registro_base(), UNIDADES, PARES_UVA)
    assert status == "validado"


def test_dose_nao_positiva_reprova():
    status, _ = validar_registro(registro_base(dose_min=0, dose_max=0), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_dose_nao_numerica_reprova():
    status, _ = validar_registro(registro_base(dose_min="30-50"), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_unidade_fora_do_vocabulario_reprova():
    status, _ = validar_registro(registro_base(dose_unidade="sacos/talhão"), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_volume_calda_sem_unidade_reprova():
    # volume_calda_min/max numérico sem volume_calda_unidade não pode ser "validado":
    # 1000 sem unidade pode ser 1000 L/ha ou 1000 mL/100L — dado ambíguo vira manual_review
    status, _ = validar_registro(registro_base(volume_calda_min=1000, volume_calda_max=1000), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_volume_calda_com_unidade_valida():
    status, _ = validar_registro(
        registro_base(volume_calda_min=1000, volume_calda_max=1000, volume_calda_unidade="L/ha"),
        UNIDADES, PARES_UVA,
    )
    assert status == "validado"


def test_par_sem_match_na_api_vira_validado_bula():
    # decisão 2026-08-18: a bula é o documento registrado — par ausente da API
    # com dose/unidade sãs entra como fonte-bula, não como reprovado
    status, _ = validar_registro(registro_base(cultura="Banana"), UNIDADES, PARES_UVA)
    assert status == "validado_bula"


def test_sem_nome_de_praga_continua_reprovando():
    r = registro_base(praga_nome_comum=None, praga_nome_cientifico=None)
    status, _ = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_match_por_nome_comum_e_enriquece_cientifico():
    r = registro_base(praga_nome_cientifico=None)
    status, enriquecido = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "validado"
    assert enriquecido["praga_nome_cientifico"] == "Uncinula necator"


def test_comum_ambiguo_vira_validado_bula_sem_enriquecer():
    # dois científicos possíveis p/ o mesmo comum: a linha da bula é fiel, mas
    # não dá para cravar a espécie — entra como fonte-bula, científico fica null
    pares = PARES_UVA + [{"cultura_norm": "uva", "praga_cientifico_norm": "outra especie",
                          "praga_comum_norm": "oidio", "praga_nome_cientifico": "Outra especie"}]
    r = registro_base(praga_nome_cientifico=None)
    status, enriquecido = validar_registro(r, UNIDADES, pares)
    assert status == "validado_bula"
    assert enriquecido["praga_nome_cientifico"] is None


def test_autor_botanico_nao_impede_match():
    r = registro_base(praga_nome_cientifico="Uncinula necator (Schwein.)")
    status, _ = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "validado"


def test_cientifico_divergente_cai_no_match_por_comum():
    # bula usa sinônimo taxonômico; o nome comum casa → validado (spec: comum OU científico)
    r = registro_base(praga_nome_cientifico="Erysiphe necator")
    status, enriquecido = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "validado"
    assert enriquecido["praga_nome_cientifico"] == "Erysiphe necator"  # o da bula é preservado
