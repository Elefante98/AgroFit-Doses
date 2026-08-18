import type { ProdutoResumo } from "./helpers.ts";

const TOKEN_URL = "https://api.cnptia.embrapa.br/token";
const BASE_URL = "https://api.cnptia.embrapa.br/agrofit/v1";

export function criarClienteApi(
  consumerKey: string,
  consumerSecret: string,
  fetchFn: typeof fetch = fetch,
) {
  let tokenCacheado: string | null = null;
  let tokenExpiraEm = 0;

  async function getToken(): Promise<string> {
    if (tokenCacheado && Date.now() < tokenExpiraEm - 60_000) return tokenCacheado;
    const basic = Buffer.from(`${consumerKey}:${consumerSecret}`).toString("base64");
    const res = await fetchFn(TOKEN_URL, {
      method: "POST",
      headers: {
        Authorization: `Basic ${basic}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: "grant_type=client_credentials",
    });
    if (!res.ok) throw new Error(`Token falhou (${res.status}): ${await res.text()}`);
    const json = (await res.json()) as { access_token: string; expires_in?: number };
    tokenCacheado = json.access_token;
    tokenExpiraEm = Date.now() + (json.expires_in ?? 3600) * 1000;
    return tokenCacheado;
  }

  async function paginaProdutos(page: number) {
    const token = await getToken();
    const res = await fetchFn(`${BASE_URL}/produtos-formulados?page=${page}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`produtos-formulados p.${page} falhou (${res.status})`);
    return {
      produtos: (await res.json()) as ProdutoResumo[],
      totalPaginas: Number(res.headers.get("X-Pages") ?? "0"),
      totalRegistros: Number(res.headers.get("X-Records-Count") ?? "0"),
    };
  }

  return { paginaProdutos };
}
