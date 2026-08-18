import json
import shutil
from pathlib import Path

from import_db import carga_extracted, carga_metadata, conectar, derivar_estado, relatorio_cobertura

FIXTURES = Path(__file__).parent / "fixtures"
UNIDADES = set(json.loads((Path(__file__).parent.parent / "unidades.json").read_text()))


def preparar(tmp_path):
    for d in ("produtos", "bulas", "pre", "extracted"):
        (tmp_path / d).mkdir()
    shutil.copy(FIXTURES / "produto_6099.json", tmp_path / "produtos" / "6099.json")
    (tmp_path / "bulas" / "6099.pdf").write_bytes(b"%PDF")
    shutil.copy(FIXTURES / "extracted_6099.json", tmp_path / "extracted" / "6099.json")
    conn = conectar(tmp_path / "doses.db")
    carga_metadata(conn, tmp_path / "produtos", tmp_path / "bulas")
    return conn, tmp_path


def test_import_parcial_valido_entra_reprovado_marca_review(tmp_path):
    conn, _ = preparar(tmp_path)
    resumo = carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    assert resumo == {"produtos": 1, "validados": 1, "manual_review": 1}

    linhas = conn.execute("SELECT praga_comum_norm, status FROM indicacoes ORDER BY status").fetchall()
    assert [(l["praga_comum_norm"], l["status"]) for l in linhas] == [
        ("ferrugem", "manual_review"), ("oidio", "validado"),
    ]


def test_flags_processada_e_incompleto(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    prod = conn.execute("SELECT processada, incompleto FROM produtos").fetchone()
    assert prod["processada"] == 1
    # pares da API: uva/oidio (validado), uva/ferrugem (só manual_review),
    # algodao/ramularia (sem registro) → incompleto
    assert prod["incompleto"] == 1


def test_reimport_idempotente(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    assert conn.execute("SELECT COUNT(*) c FROM indicacoes").fetchone()["c"] == 2


def test_cobertura(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    r = relatorio_cobertura(conn)
    assert r["pares_api"] == 3
    assert r["pares_com_dose"] == 1        # só uva/oidio tem dose validada
    assert abs(r["cobertura"] - 1 / 3) < 1e-9


def test_extracted_vazio_processada_sem_indicacoes(tmp_path):
    conn, base = preparar(tmp_path)
    (base / "extracted" / "6099.json").write_text(
        json.dumps({"numero_registro": "6099", "registros": [], "motivo": "bula sem tabela de dose"})
    )
    resumo = carga_extracted(conn, base / "extracted", UNIDADES)
    assert resumo["validados"] == 0
    assert conn.execute("SELECT processada FROM produtos").fetchone()["processada"] == 1


def test_derivar_estado_cascata(tmp_path):
    _, base = preparar(tmp_path)
    # estados são POR PRODUTO: todo reg testado precisa do seu produtos/<reg>.json
    # 6099 tem extracted e foi importado; 7777 sem bula; 8888 com .scan; 9999 só pre
    for reg in ("7777", "8888", "9999"):
        shutil.copy(FIXTURES / "produto_6099.json", base / "produtos" / f"{reg}.json")
    (base / "pre" / "8888.scan").write_bytes(b"")
    (base / "pre" / "9999.txt").write_text("=== PÁGINA 1 ===\nDOSE")
    estados = derivar_estado(base / "produtos", base / "bulas", base / "pre",
                             base / "extracted", importados={"6099"})
    assert estados["6099"] == "importada"
    assert estados["7777"] == "sem_bula"      # produto existe, bula não está em raw/bulas
    assert estados["8888"] == "manual_review"
    assert estados["9999"] == "pre_ok"


def test_estado_scan_superado_por_extracted(tmp_path):
    _, base = preparar(tmp_path)
    (base / "pre" / "6099.scan").write_bytes(b"")  # scan + extracted → extracted vence
    estados = derivar_estado(base / "produtos", base / "bulas", base / "pre",
                             base / "extracted", importados=set())
    assert estados["6099"] == "extraida"
