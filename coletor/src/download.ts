import { writeFile } from "node:fs/promises";

const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)";

/** Baixa um PDF do MAPA. Valida magic bytes %PDF antes de gravar (spec: amostragem de PDFs válidos). */
export async function baixarPdf(
  url: string,
  destino: string,
  fetchFn: typeof fetch = fetch,
): Promise<void> {
  const res = await fetchFn(url, { headers: { "User-Agent": USER_AGENT } });
  if (!res.ok) throw new Error(`download falhou (${res.status}): ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.subarray(0, 4).toString() !== "%PDF") {
    throw new Error(`corpo não é PDF: ${url}`);
  }
  await writeFile(destino, buf);
}
