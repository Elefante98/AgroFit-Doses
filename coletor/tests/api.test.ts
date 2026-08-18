import { test } from "node:test";
import assert from "node:assert/strict";
import { criarClienteApi } from "../src/api.ts";

type Chamada = { url: string; init?: RequestInit };

function fetchFalso(respostas: Record<string, () => Response>, chamadas: Chamada[]) {
  return (async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    chamadas.push({ url: u, init });
    const chave = Object.keys(respostas).find(k => u.startsWith(k));
    if (!chave) throw new Error(`sem resposta falsa para ${u}`);
    return respostas[chave]();
  }) as typeof fetch;
}

const respostaToken = () =>
  new Response(JSON.stringify({ access_token: "tok-1", expires_in: 1502 }), { status: 200 });

const respostaPagina = () =>
  new Response(JSON.stringify([{ numero_registro: "6099" }]), {
    status: 200,
    headers: { "X-Pages": "43", "X-Records-Count": "4252" },
  });

test("paginaProdutos autentica, retorna produtos e headers de paginação", async () => {
  const chamadas: Chamada[] = [];
  const cliente = criarClienteApi("k", "s", fetchFalso({
    "https://api.cnptia.embrapa.br/token": respostaToken,
    "https://api.cnptia.embrapa.br/agrofit/v1/produtos-formulados": respostaPagina,
  }, chamadas));

  const r = await cliente.paginaProdutos(1);
  assert.equal(r.produtos[0].numero_registro, "6099");
  assert.equal(r.totalPaginas, 43);
  assert.equal(r.totalRegistros, 4252);
  const auth = (chamadas[1].init?.headers as Record<string, string>).Authorization;
  assert.equal(auth, "Bearer tok-1");
});

test("token é cacheado entre páginas (uma chamada ao /token)", async () => {
  const chamadas: Chamada[] = [];
  const cliente = criarClienteApi("k", "s", fetchFalso({
    "https://api.cnptia.embrapa.br/token": respostaToken,
    "https://api.cnptia.embrapa.br/agrofit/v1/produtos-formulados": respostaPagina,
  }, chamadas));

  await cliente.paginaProdutos(1);
  await cliente.paginaProdutos(2);
  assert.equal(chamadas.filter(c => c.url.includes("/token")).length, 1);
});

test("resposta não-ok vira erro com status", async () => {
  const cliente = criarClienteApi("k", "s", fetchFalso({
    "https://api.cnptia.embrapa.br/token": respostaToken,
    "https://api.cnptia.embrapa.br/agrofit/v1/produtos-formulados":
      () => new Response("boom", { status: 500 }),
  }, []));
  await assert.rejects(() => cliente.paginaProdutos(1), /500/);
});
