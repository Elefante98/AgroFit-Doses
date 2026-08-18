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
