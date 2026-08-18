export interface DocumentoCadastrado {
  descricao?: string;
  tipo_documento: string;
  url: string;
  origem?: string;
}

export interface ProdutoResumo {
  numero_registro: string;
  documento_cadastrado?: DocumentoCadastrado[];
  [k: string]: unknown;
}

/** Bulas do produto, dedupadas por URL (a API repete o mesmo doc por origem). */
export function bulasDe(produto: ProdutoResumo): DocumentoCadastrado[] {
  const vistos = new Set<string>();
  return (produto.documento_cadastrado ?? [])
    .filter(d => (d.tipo_documento ?? "").trim().toLowerCase() === "bula")
    .filter(d => (vistos.has(d.url) ? false : (vistos.add(d.url), true)));
}

/** `<reg>.pdf` para a 1ª bula; `<reg>_2.pdf`, `_3`… para as demais (spec: nunca sobrescrever). */
export function nomeArquivoBula(numeroRegistro: string, indice: number): string {
  return indice === 0 ? `${numeroRegistro}.pdf` : `${numeroRegistro}_${indice + 1}.pdf`;
}
