"""2c: cargas do SQLite. Carga 1 (metadata) nesta task; carga 2 (indicações) na Task 8.

Invariantes (spec):
- banco 100% regenerável de raw/ + extracted/ + unidades.json;
- carga 1: INSERT quando produto não existe; UPDATE só de metadata quando existe
  (NUNCA toca processada/incompleto); ingredientes_ativos e indicacoes_api são
  apaga-e-regrava por produto — idempotente.
"""
import json
import sqlite3
from pathlib import Path

from normalizacao import normalizar, sem_autor

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schema.sql"

COLS_METADATA = [
    "marca_comercial", "marca_norm", "titular", "formulacao",
    "classificacao_toxicologica", "classificacao_ambiental",
    "url_agrofit", "bula_arquivo", "bula_url",
]


def conectar(caminho: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def _bula_de(produto: dict) -> str | None:
    vistos: set[str] = set()
    for doc in produto.get("documento_cadastrado") or []:
        url = doc.get("url")
        if doc.get("tipo_documento", "").strip().lower() == "bula" and url and url not in vistos:
            vistos.add(url)
            return url  # 1ª bula; multi_bula já foi logado pelo coletor
    return None


def _comuns(indicacao: dict) -> list[str | None]:
    comum = indicacao.get("praga_nome_comum")
    if isinstance(comum, list) and comum:
        return list(comum)
    return [None]  # a API usa a string "Ausente" quando não há nome comum


def carga_metadata(conn: sqlite3.Connection, dir_produtos: Path, dir_bulas: Path) -> int:
    n = 0
    for arq in sorted(dir_produtos.glob("*.json")):
        produto = json.loads(arq.read_text(encoding="utf-8"))
        reg = produto["numero_registro"]
        lista_marcas = produto.get("marca_comercial") or []
        marcas = "; ".join(lista_marcas)  # exibição
        # match: cada marca normalizada, separador ";" SEM espaço — o LIKE do MCP
        # usa fronteiras ';<marca>;' e um espaço no separador quebraria a 2ª marca
        marca_norm = ";".join(normalizar(m) for m in lista_marcas)
        bula_pdf = f"{reg}.pdf"
        valores = {
            "numero_registro": reg,
            "marca_comercial": marcas,
            "marca_norm": marca_norm,
            "titular": produto.get("titular_registro"),
            "formulacao": produto.get("formulacao"),
            "classificacao_toxicologica": produto.get("classificacao_toxicologica"),
            "classificacao_ambiental": produto.get("classificacao_ambiental"),
            "url_agrofit": produto.get("url_agrofit"),
            "bula_arquivo": bula_pdf if (dir_bulas / bula_pdf).exists() else None,
            "bula_url": _bula_de(produto),
        }

        existe = conn.execute(
            "SELECT 1 FROM produtos WHERE numero_registro = ?", (reg,)
        ).fetchone()
        if existe:
            sets = ", ".join(f"{c} = :{c}" for c in COLS_METADATA)
            conn.execute(f"UPDATE produtos SET {sets} WHERE numero_registro = :numero_registro", valores)
        else:
            cols = ", ".join(valores)
            marcadores = ", ".join(f":{c}" for c in valores)
            conn.execute(f"INSERT INTO produtos ({cols}) VALUES ({marcadores})", valores)

        conn.execute("DELETE FROM ingredientes_ativos WHERE produto_fk = ?", (reg,))
        for ing in produto.get("ingrediente_ativo_detalhado") or []:
            conn.execute(
                "INSERT INTO ingredientes_ativos (produto_fk, nome, grupo_quimico, concentracao, unidade)"
                " VALUES (?, ?, ?, ?, ?)",
                (reg, ing.get("ingrediente_ativo"), ing.get("grupo_quimico"),
                 ing.get("concentracao"), ing.get("unidade_medida")),
            )

        conn.execute("DELETE FROM indicacoes_api WHERE produto_fk = ?", (reg,))
        for ind in produto.get("indicacao_uso") or []:
            cientifico = ind.get("praga_nome_cientifico")
            for comum in _comuns(ind):
                conn.execute(
                    "INSERT INTO indicacoes_api (produto_fk, cultura, cultura_norm,"
                    " praga_nome_cientifico, praga_cientifico_norm, praga_nome_comum, praga_comum_norm)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (reg, ind["cultura"], normalizar(ind["cultura"]),
                     cientifico, normalizar(sem_autor(cientifico)) if cientifico else None,
                     comum, normalizar(comum) if comum else None),
                )
        n += 1
    conn.commit()
    return n


# ── Carga 2: indicações extraídas ────────────────────────────────────────────

COLS_INDICACAO = [
    "produto_fk", "cultura", "cultura_norm",
    "praga_nome_cientifico", "praga_cientifico_norm", "praga_nome_comum", "praga_comum_norm",
    "dose_min", "dose_max", "dose_unidade",
    "volume_calda_min", "volume_calda_max", "volume_calda_unidade", "volume_calda_outros",
    "num_max_aplicacoes", "intervalo_aplicacao",
    "carencia_dias", "carencia_texto", "epoca_aplicacao",
    "fonte_pagina", "fonte_trecho", "status",
]


def _linha_indicacao(reg_produto: str, registro: dict, status: str) -> dict:
    cientifico = registro.get("praga_nome_cientifico")
    comum = registro.get("praga_nome_comum")
    linha = {c: registro.get(c) for c in COLS_INDICACAO if c not in
             ("produto_fk", "cultura_norm", "praga_cientifico_norm", "praga_comum_norm", "status")}
    linha.update({
        "produto_fk": reg_produto,
        "cultura_norm": normalizar(registro.get("cultura") or ""),
        "praga_cientifico_norm": normalizar(sem_autor(cientifico)) if cientifico else None,
        "praga_comum_norm": normalizar(comum) if comum else None,
        "status": status,
    })
    return linha


def _par_tem_dose(conn: sqlite3.Connection, produto: str, par: sqlite3.Row) -> bool:
    """Par da API coberto = existe indicação validada do produto casando por científico OU comum."""
    return conn.execute(
        "SELECT 1 FROM indicacoes WHERE produto_fk = ? AND cultura_norm = ? AND status = 'validado'"
        " AND (   (praga_cientifico_norm IS NOT NULL AND praga_cientifico_norm = ?)"
        "      OR (praga_comum_norm      IS NOT NULL AND praga_comum_norm      = ?))"
        " LIMIT 1",
        (produto, par["cultura_norm"], par["praga_cientifico_norm"], par["praga_comum_norm"]),
    ).fetchone() is not None


def carga_extracted(conn: sqlite3.Connection, dir_extracted: Path, unidades: set[str]) -> dict:
    from validacao import validar_registro

    resumo = {"produtos": 0, "validados": 0, "validado_bula": 0, "manual_review": 0}
    for arq in sorted(dir_extracted.glob("*.json")):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        reg = dados["numero_registro"]
        # extracted órfão (clone com extracted/ versionado + raw/ incompleto):
        # sem o produto no banco o INSERT estouraria FK — pula com aviso
        if not conn.execute("SELECT 1 FROM produtos WHERE numero_registro = ?", (reg,)).fetchone():
            print(f"AVISO: extracted/{reg}.json sem produto em raw/ — pulado")
            continue
        pares_api = conn.execute(
            "SELECT cultura_norm, praga_cientifico_norm, praga_comum_norm, praga_nome_cientifico"
            " FROM indicacoes_api WHERE produto_fk = ?", (reg,)
        ).fetchall()

        conn.execute("DELETE FROM indicacoes WHERE produto_fk = ?", (reg,))
        for registro in dados.get("registros") or []:
            status, enriquecido = validar_registro(registro, unidades, pares_api)
            linha = _linha_indicacao(reg, enriquecido, status)
            cols = ", ".join(COLS_INDICACAO)
            marcadores = ", ".join(f":{c}" for c in COLS_INDICACAO)
            conn.execute(f"INSERT INTO indicacoes ({cols}) VALUES ({marcadores})", linha)
            chave = {"validado": "validados", "validado_bula": "validado_bula"}.get(status, "manual_review")
            resumo[chave] += 1

        # par sem NENHUM nome de praga não bloqueia (não há como casar contra ele)
        pares_nomeados = [p for p in pares_api
                          if p["praga_cientifico_norm"] or p["praga_comum_norm"]]
        incompleto = any(not _par_tem_dose(conn, reg, par) for par in pares_nomeados)
        conn.execute(
            "UPDATE produtos SET processada = 1, incompleto = ? WHERE numero_registro = ?",
            (1 if incompleto else 0, reg),
        )
        resumo["produtos"] += 1
    conn.commit()
    return resumo


# ── Estado do pipeline (derivado; ninguém escreve à mão) ─────────────────────

def derivar_estado(dir_produtos: Path, dir_bulas: Path, dir_pre: Path,
                   dir_extracted: Path, importados: set[str]) -> dict[str, str]:
    """Cascata do estado mais avançado para o mais básico — vale o primeiro que casar."""
    estados: dict[str, str] = {}
    for arq in sorted(dir_produtos.glob("*.json")):
        reg = arq.stem
        extracted = dir_extracted / f"{reg}.json"
        if reg in importados and extracted.exists():
            dados = json.loads(extracted.read_text(encoding="utf-8"))
            estados[reg] = "vazia" if not dados.get("registros") else "importada"
        elif extracted.exists():
            estados[reg] = "extraida"
        elif (dir_pre / f"{reg}.txt").exists():
            estados[reg] = "pre_ok"
        elif (dir_pre / f"{reg}.scan").exists():
            estados[reg] = "manual_review"
        elif not (dir_bulas / f"{reg}.pdf").exists():
            estados[reg] = "sem_bula"
        else:
            estados[reg] = "pendente"
    return estados


def relatorio_cobertura(conn: sqlite3.Connection, regs: set[str] | None = None) -> dict:
    """% dos pares da API (de produtos COM bula) cobertos por dose validada.

    `regs` restringe a medição a um subconjunto de produtos — é assim que o
    piloto de ~30 bulas mede sua própria cobertura (EXTRACAO.md) sem diluir o
    número nos ~4 mil produtos ainda não extraídos.
    """
    sql = (
        "SELECT a.produto_fk, a.cultura_norm, a.praga_cientifico_norm, a.praga_comum_norm"
        " FROM indicacoes_api a JOIN produtos p ON p.numero_registro = a.produto_fk"
        " WHERE p.bula_arquivo IS NOT NULL"
        " AND (a.praga_cientifico_norm IS NOT NULL OR a.praga_comum_norm IS NOT NULL)"
    )
    pares = conn.execute(sql).fetchall()
    if regs is not None:
        pares = [p for p in pares if p["produto_fk"] in regs]
    com_dose = sum(1 for par in pares if _par_tem_dose(conn, par["produto_fk"], par))
    total = len(pares)
    return {"pares_api": total, "pares_com_dose": com_dose,
            "cobertura": (com_dose / total) if total else 0.0}


def main() -> None:
    unidades = set(json.loads((Path(__file__).resolve().parent / "unidades.json").read_text()))
    dir_dados = RAIZ / "data"
    dir_dados.mkdir(exist_ok=True)
    conn = conectar(dir_dados / "doses.db")

    n = carga_metadata(conn, RAIZ / "raw" / "produtos", RAIZ / "raw" / "bulas")
    print(f"carga 1: {n} produtos")

    (RAIZ / "extracted").mkdir(exist_ok=True)
    resumo = carga_extracted(conn, RAIZ / "extracted", unidades)
    print(f"carga 2: {resumo}")

    importados = {a.stem for a in (RAIZ / "extracted").glob("*.json")}
    estados = derivar_estado(RAIZ / "raw" / "produtos", RAIZ / "raw" / "bulas",
                             RAIZ / "pre", RAIZ / "extracted", importados)
    (RAIZ / "estado.json").write_text(json.dumps(estados, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("estados:", dict(Counter(estados.values())))

    cob = relatorio_cobertura(conn)
    print(f"cobertura: {cob['pares_com_dose']}/{cob['pares_api']} = {cob['cobertura']:.1%}"
          f" (aceite: >= 90%)")


if __name__ == "__main__":
    main()
