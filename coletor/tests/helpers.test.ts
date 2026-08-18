import { test } from "node:test";
import assert from "node:assert/strict";
import { bulasDe, nomeArquivoBula, type ProdutoResumo } from "../src/helpers.ts";

const produto = (docs: object[]): ProdutoResumo =>
  ({ numero_registro: "6099", documento_cadastrado: docs } as ProdutoResumo);

test("bulasDe filtra só tipo Bula", () => {
  const p = produto([
    { tipo_documento: "Certificado", url: "https://x/cert.pdf" },
    { tipo_documento: "Bula", url: "https://x/bula.pdf" },
    { tipo_documento: "Rótulo", url: "https://x/rotulo.pdf" },
  ]);
  assert.deepEqual(bulasDe(p).map(b => b.url), ["https://x/bula.pdf"]);
});

test("bulasDe deduplica pela URL (origens repetidas não são multi-bula)", () => {
  const p = produto([
    { tipo_documento: "Bula", url: "https://x/bula.pdf", origem: "ANVISA" },
    { tipo_documento: "Bula", url: "https://x/bula.pdf", origem: "IBAMA" },
    { tipo_documento: "Bula", url: "https://x/outra.pdf", origem: "Mapa" },
  ]);
  assert.equal(bulasDe(p).length, 2);
});

test("bulasDe tolera tipo com espaços/caixa e lista ausente", () => {
  assert.equal(bulasDe(produto([{ tipo_documento: " BULA ", url: "https://x/b.pdf" }])).length, 1);
  assert.equal(bulasDe({ numero_registro: "1" } as ProdutoResumo).length, 0);
});

test("nomeArquivoBula: primeira sem sufixo, demais _2, _3…", () => {
  assert.equal(nomeArquivoBula("11023", 0), "11023.pdf");
  assert.equal(nomeArquivoBula("11023", 1), "11023_2.pdf");
  assert.equal(nomeArquivoBula("11023", 2), "11023_3.pdf");
});
