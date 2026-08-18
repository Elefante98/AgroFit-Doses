"""2a: recorta de cada bula as páginas com tabela/keywords → pre/<reg>.txt.

Bula com texto < MIN_CHARS (provável scan) vira o marcador pre/<reg>.scan.
Só processa raw/bulas/<reg>.pdf SEM sufixo (_2 etc. aguardam decisão multi_bula).
"""
import argparse
import re
import sys
from pathlib import Path

import pdfplumber

from normalizacao import normalizar

RAIZ = Path(__file__).resolve().parent.parent
DIR_BULAS = RAIZ / "raw" / "bulas"
DIR_PRE = RAIZ / "pre"
MIN_CHARS = 500
KEYWORDS = ["dose", "instrucoes de uso", "cultura", "modo de aplica", "intervalo", "carencia"]
SEM_SUFIXO = re.compile(r"^\d+\.pdf$")


def selecionar_paginas(paginas: list[dict]) -> set[int]:
    """Candidata = tem tabela OU keyword normalizada; adjacentes entram (tabelas transbordam)."""
    candidatas = {
        p["numero"]
        for p in paginas
        if p["tem_tabela"] or any(k in normalizar(p["texto"]) for k in KEYWORDS)
    }
    numeros = {p["numero"] for p in paginas}
    adjacentes = {n + d for n in candidatas for d in (-1, 1)} & numeros
    return candidatas | adjacentes


def render_pagina(numero: int, texto: str, tabelas: list[list[list[str | None]]]) -> str:
    partes = [f"=== PÁGINA {numero} ===", texto.strip()]
    for tabela in tabelas:
        partes.append("[TABELA]")
        for linha in tabela:
            partes.append(" | ".join((c or "").replace("\n", " ").strip() for c in linha))
    return "\n".join(partes)


def processar_bula(caminho_pdf: Path, dir_saida: Path) -> Path:
    reg = caminho_pdf.stem
    with pdfplumber.open(caminho_pdf) as pdf:
        paginas = []
        tabelas_por_pagina: dict[int, list] = {}
        for i, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text() or ""
            tabelas = pagina.extract_tables()
            paginas.append({"numero": i, "texto": texto, "tem_tabela": bool(tabelas)})
            tabelas_por_pagina[i] = tabelas

    total_chars = sum(len(p["texto"]) for p in paginas)
    if total_chars < MIN_CHARS:
        destino = dir_saida / f"{reg}.scan"
        destino.write_bytes(b"")
        return destino

    escolhidas = selecionar_paginas(paginas)
    blocos = [
        render_pagina(p["numero"], p["texto"], tabelas_por_pagina[p["numero"]])
        for p in paginas
        if p["numero"] in escolhidas
    ]
    destino = dir_saida / f"{reg}.txt"
    destino.write_text("\n\n".join(blocos), encoding="utf-8")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=None)
    args = parser.parse_args()

    DIR_PRE.mkdir(exist_ok=True)
    pdfs = sorted(p for p in DIR_BULAS.glob("*.pdf") if SEM_SUFIXO.match(p.name))
    feitos = 0
    for pdf_path in pdfs:
        if (DIR_PRE / f"{pdf_path.stem}.txt").exists() or (DIR_PRE / f"{pdf_path.stem}.scan").exists():
            continue
        try:
            destino = processar_bula(pdf_path, DIR_PRE)
            print(f"{pdf_path.stem} -> {destino.suffix}")
        except Exception as exc:  # PDF corrompido não derruba o lote
            print(f"{pdf_path.stem} ERRO: {exc}", file=sys.stderr)
            (DIR_PRE / f"{pdf_path.stem}.scan").write_bytes(b"")
        feitos += 1
        if args.limite and feitos >= args.limite:
            break


if __name__ == "__main__":
    main()
