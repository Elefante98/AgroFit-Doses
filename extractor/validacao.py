"""Validação de precisão (nível registro) — spec Bloco 2c.

Três saídas:
- "validado": dose/unidade sãs E par (cultura, praga) confirmado no
  indicacao_uso da API;
- "validado_bula": dose/unidade sãs, par consta só na bula (a bula é o
  documento registrado; a API não lista todos os cruzamentos) — decisão de
  produto de 2026-08-18: servido pelo MCP com proveniência explícita;
- "manual_review": dose/unidade inválidas ou nomes ausentes — retido.

Reprovado NUNCA é descartado: o humano corrige no extracted/<reg>.json.
"""
from numbers import Real

from normalizacao import normalizar, sem_autor


def _numero_positivo(v) -> bool:
    return isinstance(v, Real) and not isinstance(v, bool) and v > 0


def validar_registro(reg: dict, unidades: set[str], pares_api: list) -> tuple[str, dict]:
    saida = dict(reg)

    # dose obrigatória, numérica e > 0
    if not (_numero_positivo(reg.get("dose_min")) and _numero_positivo(reg.get("dose_max"))):
        return "manual_review", saida
    if reg.get("dose_unidade") not in unidades:
        return "manual_review", saida
    # volume de calda é opcional, mas se veio precisa ser são
    tem_volume_calda = any(reg.get(campo) is not None for campo in ("volume_calda_min", "volume_calda_max"))
    for campo in ("volume_calda_min", "volume_calda_max"):
        v = reg.get(campo)
        if v is not None and not _numero_positivo(v):
            return "manual_review", saida
    vcu = reg.get("volume_calda_unidade")
    # se veio min/max, a unidade é obrigatória (dado numérico sem unidade não é
    # "validado" — não dá pra saber se é 1000 L/ha ou 1000 mL/100L)
    if tem_volume_calda and vcu not in unidades:
        return "manual_review", saida
    if not tem_volume_calda and vcu is not None and vcu not in unidades:
        return "manual_review", saida

    # matching contra os pares autorizados da API
    cultura = normalizar(reg.get("cultura") or "")
    cientifico = reg.get("praga_nome_cientifico")
    comum = reg.get("praga_nome_comum")
    candidatos = [p for p in pares_api if p["cultura_norm"] == cultura]

    # spec: "casa por nome comum OU científico" — científico divergente (ex.:
    # sinônimo taxonômico na bula) NÃO impede o match pelo comum
    if cientifico:
        alvo = normalizar(sem_autor(cientifico))
        if any(p["praga_cientifico_norm"] == alvo for p in candidatos):
            return "validado", saida

    if comum:
        alvo = normalizar(comum)
        matches = {p["praga_cientifico_norm"]: p for p in candidatos if p["praga_comum_norm"] == alvo}
        if len(matches) == 1:
            if not cientifico:  # único → enriquece o científico a partir da API
                saida["praga_nome_cientifico"] = next(iter(matches.values()))["praga_nome_cientifico"]
            return "validado", saida  # científico da bula, se houver, é preservado

    # dose e unidade sãs, mas o par não consta na API: fonte é a bula
    if reg.get("cultura") and (cientifico or comum):
        return "validado_bula", saida

    return "manual_review", saida  # sem cultura ou sem nenhum nome de praga
