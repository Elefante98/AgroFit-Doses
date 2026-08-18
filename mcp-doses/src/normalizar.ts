/** Espelho exato de extractor/normalizacao.py — mudou lá, muda aqui. */
export function normalizar(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/\s+/g, " ");
}

/** Espelho de sem_autor(): remove o parêntese FINAL (autor botânico) do nome científico. */
export function semAutor(s: string): string {
  return s.replace(/\s*\([^)]*\)\s*$/, "").trim();
}
