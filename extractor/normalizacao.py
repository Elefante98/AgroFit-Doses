"""Normalização canônica — espelhada em mcp-doses/src/normalizar.ts. Mudou aqui, muda lá."""
import re
import unicodedata


def normalizar(s: str) -> str:
    """lowercase → trim → NFD sem diacríticos → espaços colapsados."""
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


def sem_autor(cientifico: str) -> str:
    """Remove o autor botânico: um parêntese no FIM do nome científico."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", cientifico).strip()
