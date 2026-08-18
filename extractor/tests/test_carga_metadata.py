import json
import shutil
from pathlib import Path

from import_db import carga_metadata, conectar

FIXTURES = Path(__file__).parent / "fixtures"


def preparar(tmp_path):
    dir_produtos = tmp_path / "produtos"
    dir_bulas = tmp_path / "bulas"
    dir_produtos.mkdir()
    dir_bulas.mkdir()
    shutil.copy(FIXTURES / "produto_6099.json", dir_produtos / "6099.json")
    conn = conectar(tmp_path / "doses.db")
    return conn, dir_produtos, dir_bulas


def test_carga_cria_produto_ingredientes_e_pares(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    (dir_bulas / "6099.pdf").write_bytes(b"%PDF")  # bula presente em disco

    n = carga_metadata(conn, dir_produtos, dir_bulas)
    assert n == 1

    prod = conn.execute("SELECT * FROM produtos WHERE numero_registro='6099'").fetchone()
    assert prod["marca_comercial"] == "Domark 100 EC"
    assert prod["marca_norm"] == "domark 100 ec"
    assert prod["bula_arquivo"] == "6099.pdf"
    assert prod["processada"] == 0

    assert conn.execute("SELECT COUNT(*) c FROM ingredientes_ativos").fetchone()["c"] == 1

    pares = conn.execute(
        "SELECT cultura, praga_nome_comum, praga_cientifico_norm FROM indicacoes_api ORDER BY cultura"
    ).fetchall()
    assert len(pares) == 3
    assert pares[0]["praga_nome_comum"] is None  # "Ausente" vira NULL
    assert any(p["praga_cientifico_norm"] == "uncinula necator" for p in pares)


def test_sem_bula_em_disco_fica_null(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    carga_metadata(conn, dir_produtos, dir_bulas)
    prod = conn.execute("SELECT bula_arquivo, bula_url FROM produtos").fetchone()
    assert prod["bula_arquivo"] is None
    assert prod["bula_url"] == "https://agrofit.agricultura.gov.br/bula6099.pdf"


def test_recarga_nao_duplica_nem_zera_flags(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    carga_metadata(conn, dir_produtos, dir_bulas)
    conn.execute("UPDATE produtos SET processada=1, incompleto=1")
    conn.commit()

    carga_metadata(conn, dir_produtos, dir_bulas)  # re-run
    assert conn.execute("SELECT COUNT(*) c FROM indicacoes_api").fetchone()["c"] == 3
    prod = conn.execute("SELECT processada, incompleto FROM produtos").fetchone()
    assert (prod["processada"], prod["incompleto"]) == (1, 1)  # carga 1 nunca toca flags
