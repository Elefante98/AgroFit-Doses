import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { baixarPdf } from "../src/download.ts";

const PDF_FALSO = Buffer.concat([Buffer.from("%PDF-1.7\n"), Buffer.alloc(64)]);

test("baixarPdf grava PDF válido e envia User-Agent", async () => {
  const dir = await mkdtemp(join(tmpdir(), "col-"));
  const destino = join(dir, "6099.pdf");
  let uaEnviado = "";
  const fetchFalso = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    uaEnviado = (init?.headers as Record<string, string>)["User-Agent"];
    return new Response(PDF_FALSO, { status: 200 });
  }) as typeof fetch;

  await baixarPdf("https://agrofit.agricultura.gov.br/x.pdf", destino, fetchFalso);
  assert.match(uaEnviado, /Mozilla/);
  assert.equal((await readFile(destino)).subarray(0, 4).toString(), "%PDF");
});

test("baixarPdf rejeita corpo que não é PDF (HTML de erro do MAPA)", async () => {
  const dir = await mkdtemp(join(tmpdir(), "col-"));
  const fetchFalso = (async () =>
    new Response("<html>erro</html>", { status: 200 })) as typeof fetch;
  await assert.rejects(
    () => baixarPdf("https://x/y.pdf", join(dir, "z.pdf"), fetchFalso),
    /não é PDF/,
  );
});

test("baixarPdf rejeita status não-ok", async () => {
  const dir = await mkdtemp(join(tmpdir(), "col-"));
  const fetchFalso = (async () => new Response("nf", { status: 404 })) as typeof fetch;
  await assert.rejects(() => baixarPdf("https://x/y.pdf", join(dir, "z.pdf"), fetchFalso), /404/);
});
