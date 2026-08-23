"""Gera as planilhas do piloto para conferência humana contra os PDFs.

- piloto_conferencia.csv : UMA linha por linha-de-origem única da bula
  (clones de tabela compartilhada entre culturas viram uma linha só, com a
  lista de culturas na coluna `culturas`). É o conjunto a conferir.
- piloto_completo.csv    : dump integral dos registros importados (auditoria).

Uso: python gerar_planilha.py  (depois de rodar import_db.py)
"""
import csv
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DB = RAIZ / "data" / "doses.db"

CAMPOS_BASE = [  # "produto (marca comercial)" = campo marca_comercial do registro MAPA

    "numero_registro", "produto (marca comercial)", "bula_pdf", "fonte_pagina",
    "praga_nome_comum", "praga_nome_cientifico",
    "dose_min", "dose_max", "dose_unidade",
    "volume_calda_min", "volume_calda_max", "volume_calda_unidade", "volume_calda_outros",
    "num_max_aplicacoes", "intervalo_aplicacao",
]


def main() -> None:
    regs = (RAIZ / "extractor" / "piloto.txt").read_text().split()
    marcadores = ",".join("?" * len(regs))
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # completo (auditoria)
    linhas = conn.execute(
        f"""SELECT i.*, p.marca_comercial FROM indicacoes i
            JOIN produtos p ON p.numero_registro = i.produto_fk
            WHERE i.produto_fk IN ({marcadores})
            ORDER BY i.produto_fk, i.cultura, i.praga_nome_comum""", regs).fetchall()
    with (RAIZ / "extractor" / "piloto_completo.csv").open("w", newline="", encoding="utf-8-sig") as f:
        cols = linhas[0].keys()
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for l in linhas:
            w.writerow([l[c] for c in cols])

    # conferência (agrupado por linha de origem)
    grupos = conn.execute(
        f"""SELECT i.produto_fk AS numero_registro, p.marca_comercial AS "produto (marca comercial)",
              i.produto_fk || '.pdf' AS bula_pdf, i.fonte_pagina,
              i.praga_nome_comum, i.praga_nome_cientifico,
              i.dose_min, i.dose_max, i.dose_unidade,
              i.volume_calda_min, i.volume_calda_max, i.volume_calda_unidade, i.volume_calda_outros,
              i.num_max_aplicacoes, i.intervalo_aplicacao,
              GROUP_CONCAT(DISTINCT i.cultura) AS culturas,
              COUNT(*) AS n_registros,
              MAX(i.fonte_trecho) AS fonte_trecho,
              MAX(i.status) AS status
            FROM indicacoes i JOIN produtos p ON p.numero_registro = i.produto_fk
            WHERE i.produto_fk IN ({marcadores})
            GROUP BY i.produto_fk, i.praga_nome_comum, i.praga_nome_cientifico,
              i.dose_min, i.dose_max, i.dose_unidade, i.fonte_pagina,
              i.volume_calda_min, i.volume_calda_max, i.volume_calda_unidade,
              i.volume_calda_outros, i.num_max_aplicacoes, i.intervalo_aplicacao
            ORDER BY i.produto_fk, i.fonte_pagina, i.praga_nome_comum""", regs).fetchall()
    destino = RAIZ / "extractor" / "piloto_conferencia.csv"
    with destino.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(CAMPOS_BASE + ["culturas", "n_registros", "fonte_trecho", "status",
                                  "ok_humano (S/N)", "correcao"])
        for g in grupos:
            w.writerow([g[c] for c in CAMPOS_BASE] +
                       [g["culturas"], g["n_registros"], g["fonte_trecho"], g["status"], "", ""])
    print(f"conferencia: {len(grupos)} linhas | completo: {len(linhas)} registros")


if __name__ == "__main__":
    main()
