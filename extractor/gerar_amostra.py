"""Gera a amostra de certificação humana a partir de piloto_conferencia.csv.

Regra: ~2 linhas por bula (prioridade para linhas com dose numérica),
completando até TAMANHO com sorteio uniforme sobre as demais linhas.
Determinístico (SEED) para ser reproduzível.

Uso: python gerar_amostra.py  (depois de rodar gerar_planilha.py)
"""
import csv
import random
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "extractor" / "piloto_conferencia.csv"
DESTINO = RAIZ / "extractor" / "amostra_certificacao.csv"
SEED = 2026
TAMANHO = 70
POR_BULA = 2


def main() -> None:
    with ORIGEM.open(encoding="utf-8-sig") as f:
        leitor = csv.reader(f, delimiter=";")
        cab = next(leitor)
        linhas = list(leitor)

    rnd = random.Random(SEED)
    por_bula = defaultdict(list)
    for l in linhas:
        por_bula[l[0]].append(l)

    escolhidas = []
    for reg in sorted(por_bula):
        grupo = por_bula[reg]
        com_dose = [l for l in grupo if l[6]]
        base = com_dose or grupo
        rnd.shuffle(base)
        escolhidas.extend(base[:POR_BULA])

    ids = {id(l) for l in escolhidas}
    resto = [l for l in linhas if id(l) not in ids]
    rnd.shuffle(resto)
    escolhidas.extend(resto[: max(0, TAMANHO - len(escolhidas))])
    escolhidas.sort(key=lambda l: (l[0], l[3], l[4]))

    with DESTINO.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cab)
        w.writerows(escolhidas)
    print(f"amostra: {len(escolhidas)} linhas de {len(por_bula)} bulas")


if __name__ == "__main__":
    main()
