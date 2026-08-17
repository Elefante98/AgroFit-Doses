# AgroFit Doses — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline coletor → pré-proc → import + servidor MCP que expõe doses de defensivos por (produto, cultura, praga) extraídas das bulas PDF do AgroFit, com validação e proveniência.

**Architecture:** Bloco 1 (coletor Node/TS) baixa JSONs e PDFs para `raw/`. Bloco 2a (Python) recorta páginas relevantes para `pre/`; 2b (Claude, fora deste plano — procedimento documentado na Task 9) gera `extracted/`; 2c (Python) valida e carrega o SQLite `data/doses.db`, 100% regenerável dos artefatos. Bloco 3 (Node/TS) é um MCP server que lê só o SQLite.

**Tech Stack:** Node 22 + TypeScript + tsx + node:test; Python 3.14 + pdfplumber + pytest; SQLite (better-sqlite3 no MCP, sqlite3 stdlib no Python); @modelcontextprotocol/sdk + zod (mesmas versões do `mcp-agrofit`).

**Spec:** `docs/superpowers/specs/2026-08-17-agrofit-doses-design.md` — em dúvida de comportamento, a spec manda.

## Global Constraints

- Dose NUNCA é gerada/aproximada por modelo: no MCP ela vem só de query; na extração, registro suspeito vai para `manual_review`, nunca é "corrigido de cabeça".
- Credenciais Embrapa: só via `.env` na raiz (`CONSUMER_KEY`, `CONSUMER_SECRET`) — copiar valores de `.bob/mcp.json`. `.env`, `.bob/`, `raw/`, `pre/`, `data/`, `estado.json` são gitignorados; **`extracted/` é versionado** (é onde vive a correção humana).
- Normalização canônica (idêntica em Python e TS): lowercase → trim → NFD sem diacríticos → colapsar espaços. Autor botânico: remover parêntese final de nome científico.
- Downloads do MAPA: User-Agent de navegador (`Mozilla/5.0 (Windows NT 10.0; Win64; x64)`), fetch nativo do Node (undici, HTTP/1.1).
- API: `https://api.cnptia.embrapa.br` — token em `/token` (Basic + client_credentials, expira ~25 min), dados em `/agrofit/v1`. Paginar `/produtos-formulados?page=N` até o header `X-Pages`.
- Rate limit: ≥1 s entre requisições à API/downloads.
- Testes: coletor e MCP com `node --import tsx --test`; extractor com `pytest`. Nenhuma chamada de rede em teste — rede só nos smoke steps marcados.
- Commits frequentes, mensagens `feat:`/`test:`/`docs:` como no histórico.

## File Structure

```
D:/Pragas Uva/
├── .env                      (gitignorado; CONSUMER_KEY/SECRET)
├── .gitignore                (atualizar)
├── coletor/                  Bloco 1 — Node/TS
│   ├── package.json  tsconfig.json
│   ├── src/helpers.ts        bulasDe(), nomeArquivoBula() — puras
│   ├── src/api.ts            getToken(), paginaProdutos()
│   ├── src/download.ts       baixarPdf() (magic bytes %PDF)
│   ├── src/collect.ts        main: fase produtos + fase bulas, retomável
│   └── tests/*.test.ts
├── extractor/                Blocos 2a/2c — Python
│   ├── requirements.txt      (pdfplumber, pytest)
│   ├── normalizacao.py       normalizar(), sem_autor()
│   ├── preprocess.py         2a: raw/bulas → pre/
│   ├── schema.sql            4 tabelas + índices
│   ├── validacao.py          validar_registro() — pura
│   ├── import_db.py          2c: cargas 1 e 2, flags, estado.json, cobertura
│   ├── unidades.json         vocabulário de unidades (versionado)
│   ├── EXTRACAO.md           procedimento 2b (prompt + lote)
│   └── tests/ (+ fixtures/bula_fixture.pdf, extracted_6099.json)
├── mcp-doses/                Bloco 3 — Node/TS
│   ├── package.json  tsconfig.json
│   ├── src/normalizar.ts     espelho TS da normalização
│   ├── src/queries.ts        buscarDose() etc. — puras, recebem Database
│   ├── src/index.ts          MCP server (padrão do mcp-agrofit)
│   └── tests/*.test.ts
├── raw/{produtos,bulas}/     (gitignorado) + raw/failures.jsonl
├── pre/                      (gitignorado) <reg>.txt | <reg>.scan
├── extracted/                (VERSIONADO) <reg>.json
└── data/doses.db             (gitignorado)
```

---

### Task 1: Coletor — scaffold + helpers puros

**Files:**
- Create: `coletor/package.json`, `coletor/tsconfig.json`, `coletor/src/helpers.ts`, `coletor/tests/helpers.test.ts`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `bulasDe(produto): DocumentoCadastrado[]` (bulas dedupadas por URL), `nomeArquivoBula(reg: string, indice: number): string` (`"11023.pdf"`, `"11023_2.pdf"`), tipos `DocumentoCadastrado`, `ProdutoResumo`. Usados nas Tasks 2–3.

- [ ] **Step 1: Scaffold**

`coletor/package.json`:
```json
{
  "name": "coletor-agrofit",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "collect": "tsx src/collect.ts",
    "test": "node --import tsx --test tests/*.test.ts",
    "check": "tsc --noEmit"
  },
  "devDependencies": {
    "@types/node": "^22.15.29",
    "tsx": "^4.19.0",
    "typescript": "^5.8.3"
  },
  "dependencies": {
    "dotenv": "^16.4.5"
  }
}
```

`coletor/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "module": "Node16", "moduleResolution": "node16",
    "strict": true, "skipLibCheck": true, "noEmit": true,
    "types": ["node"]
  },
  "include": ["src/**/*", "tests/**/*"]
}
```

Acrescentar ao `.gitignore` da raiz (manter linhas existentes):
```
node_modules/
raw/
pre/
data/
estado.json
*.db
.env
.bob/
```

Rodar: `cd coletor && npm install`

- [ ] **Step 2: Teste que falha**

`coletor/tests/helpers.test.ts`:
```ts
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
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd coletor && npm test`
Expected: FAIL (cannot find module `../src/helpers.ts`)

- [ ] **Step 4: Implementar**

`coletor/src/helpers.ts`:
```ts
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
    .filter(d => d.tipo_documento.trim().toLowerCase() === "bula")
    .filter(d => (vistos.has(d.url) ? false : (vistos.add(d.url), true)));
}

/** `<reg>.pdf` para a 1ª bula; `<reg>_2.pdf`, `_3`… para as demais (spec: nunca sobrescrever). */
export function nomeArquivoBula(numeroRegistro: string, indice: number): string {
  return indice === 0 ? `${numeroRegistro}.pdf` : `${numeroRegistro}_${indice + 1}.pdf`;
}
```

- [ ] **Step 5: Rodar e ver passar** — `npm test` → 4 pass. `npm run check` → sem erros.

- [ ] **Step 6: Commit**
```bash
git add coletor .gitignore
git commit -m "feat: coletor scaffold + helpers de bula (dedup por URL, sufixo multi-bula)"
```

---

### Task 2: Coletor — cliente da API (token + paginação)

**Files:**
- Create: `coletor/src/api.ts`, `coletor/tests/api.test.ts`

**Interfaces:**
- Consumes: nada de Task 1 (módulo independente).
- Produces: `criarClienteApi(chave: string, segredo: string, fetchFn?: typeof fetch)` → `{ paginaProdutos(page: number): Promise<{ produtos: ProdutoResumo[]; totalPaginas: number; totalRegistros: number }> }`. Usado na Task 3. `fetchFn` injetável = testável sem rede.

- [ ] **Step 1: Teste que falha**

`coletor/tests/api.test.ts`:
```ts
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
```

- [ ] **Step 2: Rodar e ver falhar** — `npm test` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar**

`coletor/src/api.ts` (mesmo padrão de token do `mcp-agrofit/src/index.ts:40-69`, encapsulado):
```ts
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
```

- [ ] **Step 4: Rodar e ver passar** — `npm test` → 7 pass (4 da Task 1 + 3). `npm run check`.

- [ ] **Step 5: Commit**
```bash
git add coletor/src/api.ts coletor/tests/api.test.ts
git commit -m "feat: cliente da API AgroFit com token cacheado e fetch injetável"
```

---

### Task 3: Coletor — download de PDF + main retomável + smoke real

**Files:**
- Create: `coletor/src/download.ts`, `coletor/src/collect.ts`, `coletor/tests/download.test.ts`, `.env`

**Interfaces:**
- Consumes: `criarClienteApi` (Task 2), `bulasDe`/`nomeArquivoBula` (Task 1).
- Produces: CLI `npm run collect -- [--paginas N] [--pular-bulas]`; layout de `raw/` que as Tasks 5–6 leem: `raw/produtos/<reg>.json` (objeto do produto como veio da API), `raw/bulas/<reg>.pdf`, `raw/failures.jsonl` (linhas `{"tipo","numero_registro","url?","erro?"}`).

- [ ] **Step 1: Teste que falha**

`coletor/tests/download.test.ts`:
```ts
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
```

- [ ] **Step 2: Rodar e ver falhar** — `npm test` → FAIL.

- [ ] **Step 3: Implementar download**

`coletor/src/download.ts`:
```ts
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
```

- [ ] **Step 4: Rodar e ver passar** — `npm test` → 10 pass.

- [ ] **Step 5: Implementar o main**

Criar `.env` na raiz (copiar valores de `.bob/mcp.json` — **não commitar**):
```
CONSUMER_KEY=<valor de .bob/mcp.json>
CONSUMER_SECRET=<valor de .bob/mcp.json>
```

`coletor/src/collect.ts`:
```ts
import "dotenv/config";
import { appendFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { criarClienteApi } from "./api.ts";
import { bulasDe, nomeArquivoBula, type ProdutoResumo } from "./helpers.ts";
import { baixarPdf } from "./download.ts";

const RAIZ = resolve(import.meta.dirname, "..", "..");
const DIR_PRODUTOS = join(RAIZ, "raw", "produtos");
const DIR_BULAS = join(RAIZ, "raw", "bulas");
const ARQ_FALHAS = join(RAIZ, "raw", "failures.jsonl");
const PAUSA_MS = 1000;

const pausa = () => new Promise(r => setTimeout(r, PAUSA_MS));

async function registrarFalha(falha: Record<string, unknown>) {
  await appendFile(ARQ_FALHAS, JSON.stringify(falha) + "\n");
}

async function faseProdutos(cliente: ReturnType<typeof criarClienteApi>, maxPaginas?: number) {
  let pagina = 1;
  let totalPaginas = Infinity;
  let totalRegistros = 0;
  while (pagina <= Math.min(totalPaginas, maxPaginas ?? Infinity)) {
    const r = await cliente.paginaProdutos(pagina);
    totalPaginas = r.totalPaginas;
    totalRegistros = r.totalRegistros;
    for (const p of r.produtos) {
      const destino = join(DIR_PRODUTOS, `${p.numero_registro}.json`);
      if (!existsSync(destino)) {
        await writeFile(destino, JSON.stringify(p, null, 1));
      }
    }
    console.log(`página ${pagina}/${totalPaginas} ok`);
    pagina++;
    await pausa();
  }
  return totalRegistros;
}

async function faseBulas() {
  const arquivos = (await readdir(DIR_PRODUTOS)).filter(a => a.endsWith(".json"));
  let baixadas = 0;
  for (const arq of arquivos) {
    const produto: ProdutoResumo = JSON.parse(await readFile(join(DIR_PRODUTOS, arq), "utf8"));
    const bulas = bulasDe(produto);
    if (bulas.length > 1) {
      await registrarFalha({ tipo: "multi_bula", numero_registro: produto.numero_registro, total: bulas.length });
    }
    for (let i = 0; i < bulas.length; i++) {
      const destino = join(DIR_BULAS, nomeArquivoBula(produto.numero_registro, i));
      if (existsSync(destino)) continue;
      try {
        await baixarPdf(bulas[i].url, destino);
        baixadas++;
      } catch (err) {
        await registrarFalha({
          tipo: "download_falhou",
          numero_registro: produto.numero_registro,
          url: bulas[i].url,
          erro: String(err),
        });
      }
      await pausa();
    }
  }
  return baixadas;
}

async function main() {
  const chave = process.env.CONSUMER_KEY;
  const segredo = process.env.CONSUMER_SECRET;
  if (!chave || !segredo) {
    console.error("CONSUMER_KEY/CONSUMER_SECRET ausentes (defina no .env da raiz).");
    process.exit(1);
  }
  await mkdir(DIR_PRODUTOS, { recursive: true });
  await mkdir(DIR_BULAS, { recursive: true });

  const args = process.argv.slice(2);
  const iPaginas = args.indexOf("--paginas");
  const maxPaginas = iPaginas >= 0 ? Number(args[iPaginas + 1]) : undefined;

  const cliente = criarClienteApi(chave, segredo);
  const totalRegistros = await faseProdutos(cliente, maxPaginas);

  const totalLocal = (await readdir(DIR_PRODUTOS)).filter(a => a.endsWith(".json")).length;
  console.log(`produtos locais: ${totalLocal} / API: ${totalRegistros}`);
  if (maxPaginas === undefined && totalLocal < totalRegistros) {
    console.warn("ATENÇÃO: contagem local menor que X-Records-Count — re-rode para completar.");
  }

  if (!args.includes("--pular-bulas")) {
    const baixadas = await faseBulas();
    console.log(`bulas baixadas nesta execução: ${baixadas}`);
  }
}

main().catch(err => {
  console.error("Erro fatal:", err);
  process.exit(1);
});
```

- [ ] **Step 6: Typecheck** — `npm run check` → sem erros.

- [ ] **Step 7: SMOKE REAL (rede, ~2 min)** — valida integração de verdade com 1 página:

Run: `cd coletor && npm run collect -- --paginas 1`
Expected: `página 1/43 ok`, `produtos locais: 100 / API: 4252` (números atuais podem variar), dezenas de PDFs em `raw/bulas/`, eventuais linhas em `raw/failures.jsonl` só de downloads pontuais. Verificar: `ls ../raw/bulas | head` e abrir 1 PDF.

- [ ] **Step 8: Commit**
```bash
git add coletor/src/download.ts coletor/src/collect.ts coletor/tests/download.test.ts
git commit -m "feat: coletor completo — fases produtos/bulas, retomável, failures.jsonl"
```

---

### Task 4: Extractor — scaffold Python + normalização canônica

**Files:**
- Create: `extractor/requirements.txt`, `extractor/normalizacao.py`, `extractor/tests/test_normalizacao.py`, `extractor/pytest.ini`

**Interfaces:**
- Produces: `normalizar(s: str) -> str` (lowercase, trim, sem diacríticos, espaços colapsados), `sem_autor(cientifico: str) -> str` (remove parêntese final). Usadas nas Tasks 5–8; espelhadas em TS na Task 10.

- [ ] **Step 1: Scaffold**

`extractor/requirements.txt`:
```
pdfplumber>=0.11
pytest>=8
```
`extractor/pytest.ini`:
```ini
[pytest]
testpaths = tests
```
Run: `cd extractor && pip install -r requirements.txt`

- [ ] **Step 2: Teste que falha**

`extractor/tests/test_normalizacao.py`:
```python
from normalizacao import normalizar, sem_autor


def test_normalizar_caixa_acento_espacos():
    assert normalizar("  Oídio ") == "oidio"
    assert normalizar("CANA-DE-AÇÚCAR") == "cana-de-acucar"
    assert normalizar("Uva  de   mesa") == "uva de mesa"


def test_normalizar_vazio():
    assert normalizar("") == ""


def test_sem_autor_remove_parentese_final():
    assert sem_autor("Ageratum conyzoides (L.)") == "Ageratum conyzoides"
    assert sem_autor("Uncinula necator") == "Uncinula necator"


def test_sem_autor_nao_remove_parentese_no_meio():
    # parêntese interno (subgênero) não é autor — só o final sai
    assert sem_autor("Praga (Sub) nome (Autor, 1900)") == "Praga (Sub) nome"
```

- [ ] **Step 3: Rodar e ver falhar** — `cd extractor && python -m pytest -q` → erro de import.

- [ ] **Step 4: Implementar**

`extractor/normalizacao.py`:
```python
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
```

- [ ] **Step 5: Rodar e ver passar** — `python -m pytest -q` → 4 passed.

- [ ] **Step 6: Commit**
```bash
git add extractor
git commit -m "feat: extractor scaffold + normalização canônica (py)"
```

---

### Task 5: Extractor — pré-processamento 2a (bulas → pre/)

**Files:**
- Create: `extractor/preprocess.py`, `extractor/tests/test_preprocess.py`, `extractor/tests/fixtures/bula_fixture.pdf`

**Interfaces:**
- Consumes: `normalizar` (Task 4); `raw/bulas/<reg>.pdf` (Task 3).
- Produces: `pre/<reg>.txt` no formato `=== PÁGINA N ===\n<texto>\n[TABELA]\n<linhas com " | ">…` **ou** `pre/<reg>.scan` (marcador vazio, texto < 500 chars). Funções puras: `selecionar_paginas(paginas: list[dict]) -> set[int]` (dict: `{"numero": int, "texto": str, "tem_tabela": bool}`), `render_pagina(numero, texto, tabelas) -> str`. CLI: `python preprocess.py [--limite N]`.

- [ ] **Step 1: Obter fixture (rede, uma vez)**

```bash
mkdir -p extractor/tests/fixtures
curl -sL --http1.1 -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" "https://agrofit.agricultura.gov.br/agrofit_cons/agrofit.ap_download_blob_agrofit?p_id_file=532248&p_nm_file=F908909962/Bula_Domark%20100%20EC_Formata%C3%A7%C3%A3o%20textual.pdf" -o extractor/tests/fixtures/bula_fixture.pdf
```
Verificar: arquivo ~660 KB começando com `%PDF`. (Bula pública do MAPA — produto Domark 100 EC, reg. 6099, tem tabela de dose para Uva; ok versionar como fixture.)

- [ ] **Step 2: Teste que falha**

`extractor/tests/test_preprocess.py`:
```python
from pathlib import Path

from preprocess import processar_bula, selecionar_paginas

FIXTURE = Path(__file__).parent / "fixtures" / "bula_fixture.pdf"


def pag(numero, texto, tem_tabela=False):
    return {"numero": numero, "texto": texto, "tem_tabela": tem_tabela}


def test_seleciona_por_keyword_normalizada():
    paginas = [pag(1, "capa do produto"), pag(2, "MODO DE APLICAÇÃO e doses")]
    assert selecionar_paginas(paginas) == {2}


def test_seleciona_por_tabela_e_adjacentes():
    paginas = [pag(1, "x"), pag(2, "y", tem_tabela=True), pag(3, "z"), pag(4, "w")]
    # página 2 (tabela) + adjacentes 1 e 3; página 4 fica fora
    assert selecionar_paginas(paginas) == {1, 2, 3}


def test_nada_casa_nada_sai():
    assert selecionar_paginas([pag(1, "só capa"), pag(2, "endereço")]) == set()


def test_processar_bula_real_gera_txt_com_paginas_e_dose(tmp_path):
    destino = processar_bula(FIXTURE, tmp_path)
    assert destino.suffix == ".txt"
    conteudo = destino.read_text(encoding="utf-8")
    assert "=== PÁGINA" in conteudo
    assert "DOSE" in conteudo.upper()
    assert "Uva" in conteudo  # a tabela de Uva do Domark precisa sobreviver ao recorte


def test_bula_curta_vira_scan(tmp_path):
    # PDF mínimo válido de 1 página em branco (sem texto)
    import pdfplumber  # noqa: F401  (garante dep presente)
    vazio = tmp_path / "vazio.pdf"
    vazio.write_bytes(_pdf_uma_pagina_em_branco())
    destino = processar_bula(vazio, tmp_path)
    assert destino.suffix == ".scan"
    assert destino.read_bytes() == b""


def _pdf_uma_pagina_em_branco() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF"
    )
```

- [ ] **Step 3: Rodar e ver falhar** — `python -m pytest tests/test_preprocess.py -q` → erro de import.

- [ ] **Step 4: Implementar**

`extractor/preprocess.py`:
```python
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
```

- [ ] **Step 5: Rodar e ver passar** — `python -m pytest -q` → 9 passed (4 + 5).

- [ ] **Step 6: Smoke local (sem rede)** — usa as bulas do smoke da Task 3:

Run: `python preprocess.py --limite 5`
Expected: 5 linhas `<reg> -> .txt` (ou `.scan`); conferir um `pre/<reg>.txt` no editor: tem `=== PÁGINA` e a tabela de doses.

- [ ] **Step 7: Commit**
```bash
git add extractor
git commit -m "feat: pré-processamento 2a — seleção de páginas, render com tabelas, marcador .scan"
```

---

### Task 6: Extractor — schema SQLite + carga 1 (metadata)

**Files:**
- Create: `extractor/schema.sql`, `extractor/import_db.py`, `extractor/tests/test_carga_metadata.py`, `extractor/tests/fixtures/produto_6099.json`

**Interfaces:**
- Consumes: `normalizar`, `sem_autor` (Task 4); `raw/produtos/<reg>.json` (Task 3).
- Produces: `data/doses.db` com as 4 tabelas; funções `conectar(caminho: Path) -> sqlite3.Connection` (aplica schema, liga FKs), `carga_metadata(conn, dir_produtos: Path, dir_bulas: Path) -> int`. A Task 8 acrescenta a carga 2 no mesmo módulo; a Task 10 lê este schema.
- Colunas `*_norm` existem porque SQLite não tem unaccent — o matching (import e MCP) compara com elas.

- [ ] **Step 1: Fixture**

Criar `extractor/tests/fixtures/produto_6099.json` — subconjunto real do formato da API (campos que a carga usa; `marca_comercial` é lista, `praga_nome_comum` é lista OU a string `"Ausente"`):
```json
{
  "numero_registro": "6099",
  "marca_comercial": ["Domark 100 EC"],
  "titular_registro": "Gowan Produtos Agrícolas Ltda.",
  "formulacao": "EC - Concentrado Emulsionável",
  "classificacao_toxicologica": "Categoria 4",
  "classificacao_ambiental": "III - Produto Perigoso ao Meio Ambiente",
  "url_agrofit": "https://agrofit.agricultura.gov.br/agrofit_cons/!ap_produto_form_detalhe_cons?p_nr_registro=6099",
  "ingrediente_ativo_detalhado": [
    {"ingrediente_ativo": "tetraconazol", "grupo_quimico": "triazol", "concentracao": "100", "unidade_medida": "Gramas por Litros"}
  ],
  "indicacao_uso": [
    {"cultura": "Uva", "praga_nome_cientifico": "Uncinula necator", "praga_nome_comum": ["Oídio"]},
    {"cultura": "Uva", "praga_nome_cientifico": "Phakopsora euvitis", "praga_nome_comum": ["Ferrugem-da-videira"]},
    {"cultura": "Algodão", "praga_nome_cientifico": "Ramularia areola", "praga_nome_comum": "Ausente"}
  ],
  "documento_cadastrado": [
    {"tipo_documento": "Bula", "url": "https://agrofit.agricultura.gov.br/bula6099.pdf", "descricao": "Bula"}
  ]
}
```

- [ ] **Step 2: Teste que falha**

`extractor/tests/test_carga_metadata.py`:
```python
import json
import shutil
from pathlib import Path

from import_db import carga_metadata, conectar

FIXTURES = Path(__file__).parent / "fixtures"


def preparar(tmp_path):
    dir_produtos = tmp_path / "produtos"
    dir_bulas = tmp_path / "bulas"
    dir_produtos.mkdir()
    dir_bulas.mkdir()
    shutil.copy(FIXTURES / "produto_6099.json", dir_produtos / "6099.json")
    conn = conectar(tmp_path / "doses.db")
    return conn, dir_produtos, dir_bulas


def test_carga_cria_produto_ingredientes_e_pares(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    (dir_bulas / "6099.pdf").write_bytes(b"%PDF")  # bula presente em disco

    n = carga_metadata(conn, dir_produtos, dir_bulas)
    assert n == 1

    prod = conn.execute("SELECT * FROM produtos WHERE numero_registro='6099'").fetchone()
    assert prod["marca_comercial"] == "Domark 100 EC"
    assert prod["marca_norm"] == "domark 100 ec"
    assert prod["bula_arquivo"] == "6099.pdf"
    assert prod["processada"] == 0

    assert conn.execute("SELECT COUNT(*) c FROM ingredientes_ativos").fetchone()["c"] == 1

    pares = conn.execute(
        "SELECT cultura, praga_nome_comum, praga_cientifico_norm FROM indicacoes_api ORDER BY cultura"
    ).fetchall()
    assert len(pares) == 3
    assert pares[0]["praga_nome_comum"] is None  # "Ausente" vira NULL
    assert any(p["praga_cientifico_norm"] == "uncinula necator" for p in pares)


def test_sem_bula_em_disco_fica_null(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    carga_metadata(conn, dir_produtos, dir_bulas)
    prod = conn.execute("SELECT bula_arquivo, bula_url FROM produtos").fetchone()
    assert prod["bula_arquivo"] is None
    assert prod["bula_url"] == "https://agrofit.agricultura.gov.br/bula6099.pdf"


def test_recarga_nao_duplica_nem_zera_flags(tmp_path):
    conn, dir_produtos, dir_bulas = preparar(tmp_path)
    carga_metadata(conn, dir_produtos, dir_bulas)
    conn.execute("UPDATE produtos SET processada=1, incompleto=1")
    conn.commit()

    carga_metadata(conn, dir_produtos, dir_bulas)  # re-run
    assert conn.execute("SELECT COUNT(*) c FROM indicacoes_api").fetchone()["c"] == 3
    prod = conn.execute("SELECT processada, incompleto FROM produtos").fetchone()
    assert (prod["processada"], prod["incompleto"]) == (1, 1)  # carga 1 nunca toca flags
```

- [ ] **Step 3: Rodar e ver falhar** — `python -m pytest tests/test_carga_metadata.py -q` → erro de import.

- [ ] **Step 4: Implementar schema**

`extractor/schema.sql`:
```sql
CREATE TABLE IF NOT EXISTS produtos (
  numero_registro TEXT PRIMARY KEY,
  marca_comercial TEXT,            -- lista da API unida com "; "
  marca_norm      TEXT,            -- normalizada, "; " preservado p/ match por marca
  titular         TEXT,
  formulacao      TEXT,
  classificacao_toxicologica TEXT,
  classificacao_ambiental    TEXT,
  url_agrofit  TEXT,
  bula_arquivo TEXT,               -- NULL = sem bula em raw/bulas
  bula_url     TEXT,
  processada  INTEGER NOT NULL DEFAULT 0,  -- 1 = bula passou pelo import (proxy p/ MCP)
  incompleto  INTEGER NOT NULL DEFAULT 0   -- validação inversa achou par sem dose
);

CREATE TABLE IF NOT EXISTS ingredientes_ativos (
  id INTEGER PRIMARY KEY,
  produto_fk TEXT NOT NULL REFERENCES produtos(numero_registro),
  nome TEXT, grupo_quimico TEXT, concentracao TEXT, unidade TEXT
);

-- Pares (cultura, praga) autorizados segundo a API: fonte da validação inversa
-- e da detecção de lacunas em consultas cultura+praga. Um registro por nome comum
-- (par sem nome comum → uma linha com NULL).
CREATE TABLE IF NOT EXISTS indicacoes_api (
  id INTEGER PRIMARY KEY,
  produto_fk TEXT NOT NULL REFERENCES produtos(numero_registro),
  cultura TEXT NOT NULL,
  cultura_norm TEXT NOT NULL,
  praga_nome_cientifico TEXT,
  praga_cientifico_norm TEXT,
  praga_nome_comum TEXT,
  praga_comum_norm TEXT
);

CREATE TABLE IF NOT EXISTS indicacoes (
  id INTEGER PRIMARY KEY,
  produto_fk TEXT NOT NULL REFERENCES produtos(numero_registro),
  cultura TEXT NOT NULL,
  cultura_norm TEXT NOT NULL,
  praga_nome_cientifico TEXT,
  praga_cientifico_norm TEXT,
  praga_nome_comum TEXT,
  praga_comum_norm TEXT,
  dose_min REAL, dose_max REAL,          -- valor único → min = max
  dose_unidade TEXT,
  volume_calda_min REAL, volume_calda_max REAL,  -- idem
  volume_calda_unidade TEXT,
  num_max_aplicacoes INTEGER,
  intervalo_aplicacao TEXT,
  carencia_dias INTEGER,                 -- NULL quando não numérico…
  carencia_texto TEXT,                   -- …e o texto original vem aqui
  epoca_aplicacao TEXT,
  fonte_pagina INTEGER,
  fonte_trecho TEXT,
  status TEXT NOT NULL CHECK (status IN ('validado', 'manual_review'))
);

CREATE INDEX IF NOT EXISTS idx_ind_cultura_praga
  ON indicacoes (cultura_norm, praga_comum_norm, praga_cientifico_norm);
CREATE INDEX IF NOT EXISTS idx_api_cultura_praga
  ON indicacoes_api (cultura_norm, praga_comum_norm, praga_cientifico_norm);
CREATE INDEX IF NOT EXISTS idx_ind_produto ON indicacoes (produto_fk);
CREATE INDEX IF NOT EXISTS idx_api_produto ON indicacoes_api (produto_fk);
```

- [ ] **Step 5: Implementar carga 1**

`extractor/import_db.py`:
```python
"""2c: cargas do SQLite. Carga 1 (metadata) nesta task; carga 2 (indicações) na Task 8.

Invariantes (spec):
- banco 100% regenerável de raw/ + extracted/ + unidades.json;
- carga 1: INSERT quando produto não existe; UPDATE só de metadata quando existe
  (NUNCA toca processada/incompleto); ingredientes_ativos e indicacoes_api são
  apaga-e-regrava por produto — idempotente.
"""
import json
import sqlite3
from pathlib import Path

from normalizacao import normalizar, sem_autor

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schema.sql"

COLS_METADATA = [
    "marca_comercial", "marca_norm", "titular", "formulacao",
    "classificacao_toxicologica", "classificacao_ambiental",
    "url_agrofit", "bula_arquivo", "bula_url",
]


def conectar(caminho: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def _bula_de(produto: dict) -> str | None:
    vistos: set[str] = set()
    for doc in produto.get("documento_cadastrado") or []:
        if doc.get("tipo_documento", "").strip().lower() == "bula" and doc["url"] not in vistos:
            vistos.add(doc["url"])
            return doc["url"]  # 1ª bula; multi_bula já foi logado pelo coletor
    return None


def _comuns(indicacao: dict) -> list[str | None]:
    comum = indicacao.get("praga_nome_comum")
    if isinstance(comum, list) and comum:
        return list(comum)
    return [None]  # a API usa a string "Ausente" quando não há nome comum


def carga_metadata(conn: sqlite3.Connection, dir_produtos: Path, dir_bulas: Path) -> int:
    n = 0
    for arq in sorted(dir_produtos.glob("*.json")):
        produto = json.loads(arq.read_text(encoding="utf-8"))
        reg = produto["numero_registro"]
        marcas = "; ".join(produto.get("marca_comercial") or [])
        bula_pdf = f"{reg}.pdf"
        valores = {
            "numero_registro": reg,
            "marca_comercial": marcas,
            "marca_norm": normalizar(marcas),
            "titular": produto.get("titular_registro"),
            "formulacao": produto.get("formulacao"),
            "classificacao_toxicologica": produto.get("classificacao_toxicologica"),
            "classificacao_ambiental": produto.get("classificacao_ambiental"),
            "url_agrofit": produto.get("url_agrofit"),
            "bula_arquivo": bula_pdf if (dir_bulas / bula_pdf).exists() else None,
            "bula_url": _bula_de(produto),
        }

        existe = conn.execute(
            "SELECT 1 FROM produtos WHERE numero_registro = ?", (reg,)
        ).fetchone()
        if existe:
            sets = ", ".join(f"{c} = :{c}" for c in COLS_METADATA)
            conn.execute(f"UPDATE produtos SET {sets} WHERE numero_registro = :numero_registro", valores)
        else:
            cols = ", ".join(valores)
            marcadores = ", ".join(f":{c}" for c in valores)
            conn.execute(f"INSERT INTO produtos ({cols}) VALUES ({marcadores})", valores)

        conn.execute("DELETE FROM ingredientes_ativos WHERE produto_fk = ?", (reg,))
        for ing in produto.get("ingrediente_ativo_detalhado") or []:
            conn.execute(
                "INSERT INTO ingredientes_ativos (produto_fk, nome, grupo_quimico, concentracao, unidade)"
                " VALUES (?, ?, ?, ?, ?)",
                (reg, ing.get("ingrediente_ativo"), ing.get("grupo_quimico"),
                 ing.get("concentracao"), ing.get("unidade_medida")),
            )

        conn.execute("DELETE FROM indicacoes_api WHERE produto_fk = ?", (reg,))
        for ind in produto.get("indicacao_uso") or []:
            cientifico = ind.get("praga_nome_cientifico")
            for comum in _comuns(ind):
                conn.execute(
                    "INSERT INTO indicacoes_api (produto_fk, cultura, cultura_norm,"
                    " praga_nome_cientifico, praga_cientifico_norm, praga_nome_comum, praga_comum_norm)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (reg, ind["cultura"], normalizar(ind["cultura"]),
                     cientifico, normalizar(sem_autor(cientifico)) if cientifico else None,
                     comum, normalizar(comum) if comum else None),
                )
        n += 1
    conn.commit()
    return n
```

- [ ] **Step 6: Rodar e ver passar** — `python -m pytest -q` → 12 passed.

- [ ] **Step 7: Commit**
```bash
git add extractor
git commit -m "feat: schema SQLite + carga 1 de metadata (produtos, ingredientes, indicacoes_api)"
```

---

### Task 7: Extractor — validação de registros extraídos (pura)

**Files:**
- Create: `extractor/validacao.py`, `extractor/tests/test_validacao.py`, `extractor/unidades.json`

**Interfaces:**
- Consumes: `normalizar`, `sem_autor` (Task 4).
- Produces: `validar_registro(reg: dict, unidades: set[str], pares_api: list[sqlite3.Row | dict]) -> tuple[str, dict]` — retorna `("validado" | "manual_review", registro_enriquecido)`. `pares_api` são dicts com chaves `cultura_norm`, `praga_cientifico_norm`, `praga_comum_norm`, `praga_nome_cientifico`. Usada na Task 8. Formato do registro extraído (contrato com o 2b, Task 9):

```json
{
  "cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
  "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
  "volume_calda_min": 1000, "volume_calda_max": 1200, "volume_calda_unidade": "L/ha",
  "num_max_aplicacoes": 4, "intervalo_aplicacao": "7 a 15 dias",
  "carencia_dias": 7, "carencia_texto": null,
  "epoca_aplicacao": "preventivo, a partir do estádio 09 Eichhorn-Lorenz",
  "fonte_pagina": 4, "fonte_trecho": "UVA | Oídio | Uncinula necator | - | 30 | 1000 - 1200"
}
```
(Campos ausentes/desconhecidos na bula = `null`. `dose_*` são os únicos obrigatórios além de `cultura`.)

- [ ] **Step 1: Criar vocabulário**

`extractor/unidades.json` (seed medido na amostra; o ciclo de extensão é: unidade legítima nova → adicionar aqui → re-rodar import):
```json
["L/ha", "mL/ha", "kg/ha", "g/ha", "mL/100L", "g/100L", "L/100L",
 "g/planta", "mL/planta", "L/planta", "mL/100kg sementes", "g/100kg sementes",
 "g/m2", "mL/m2"]
```

- [ ] **Step 2: Teste que falha**

`extractor/tests/test_validacao.py`:
```python
import json
from pathlib import Path

from validacao import validar_registro

UNIDADES = set(json.loads((Path(__file__).parent.parent / "unidades.json").read_text()))

PARES_UVA = [
    {"cultura_norm": "uva", "praga_cientifico_norm": "uncinula necator",
     "praga_comum_norm": "oidio", "praga_nome_cientifico": "Uncinula necator"},
    {"cultura_norm": "uva", "praga_cientifico_norm": "phakopsora euvitis",
     "praga_comum_norm": "ferrugem-da-videira", "praga_nome_cientifico": "Phakopsora euvitis"},
]


def registro_base(**extra):
    r = {"cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
         "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
         "fonte_pagina": 4, "fonte_trecho": "UVA | Oídio | 30"}
    r.update(extra)
    return r


def test_registro_valido():
    status, _ = validar_registro(registro_base(), UNIDADES, PARES_UVA)
    assert status == "validado"


def test_dose_nao_positiva_reprova():
    status, _ = validar_registro(registro_base(dose_min=0, dose_max=0), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_dose_nao_numerica_reprova():
    status, _ = validar_registro(registro_base(dose_min="30-50"), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_unidade_fora_do_vocabulario_reprova():
    status, _ = validar_registro(registro_base(dose_unidade="sacos/talhão"), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_par_sem_match_na_api_reprova():
    status, _ = validar_registro(registro_base(cultura="Banana"), UNIDADES, PARES_UVA)
    assert status == "manual_review"


def test_match_por_nome_comum_e_enriquece_cientifico():
    r = registro_base(praga_nome_cientifico=None)
    status, enriquecido = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "validado"
    assert enriquecido["praga_nome_cientifico"] == "Uncinula necator"


def test_comum_ambiguo_reprova():
    pares = PARES_UVA + [{"cultura_norm": "uva", "praga_cientifico_norm": "outra especie",
                          "praga_comum_norm": "oidio", "praga_nome_cientifico": "Outra especie"}]
    r = registro_base(praga_nome_cientifico=None)
    status, _ = validar_registro(r, UNIDADES, pares)
    assert status == "manual_review"


def test_autor_botanico_nao_impede_match():
    r = registro_base(praga_nome_cientifico="Uncinula necator (Schwein.)")
    status, _ = validar_registro(r, UNIDADES, PARES_UVA)
    assert status == "validado"
```

- [ ] **Step 3: Rodar e ver falhar** — `python -m pytest tests/test_validacao.py -q` → erro de import.

- [ ] **Step 4: Implementar**

`extractor/validacao.py`:
```python
"""Validação de precisão (nível registro) — spec Bloco 2c.

Reprovado NUNCA é descartado: vira status manual_review e o humano corrige
no extracted/<reg>.json (nunca no banco).
"""
from numbers import Real

from normalizacao import normalizar, sem_autor


def _numero_positivo(v) -> bool:
    return isinstance(v, Real) and not isinstance(v, bool) and v > 0


def validar_registro(reg: dict, unidades: set[str], pares_api: list) -> tuple[str, dict]:
    saida = dict(reg)

    # dose obrigatória, numérica e > 0
    if not (_numero_positivo(reg.get("dose_min")) and _numero_positivo(reg.get("dose_max"))):
        return "manual_review", saida
    if reg.get("dose_unidade") not in unidades:
        return "manual_review", saida
    # volume de calda é opcional, mas se veio precisa ser são
    for campo in ("volume_calda_min", "volume_calda_max"):
        v = reg.get(campo)
        if v is not None and not _numero_positivo(v):
            return "manual_review", saida
    vcu = reg.get("volume_calda_unidade")
    if vcu is not None and vcu not in unidades:
        return "manual_review", saida

    # matching contra os pares autorizados da API
    cultura = normalizar(reg.get("cultura") or "")
    cientifico = reg.get("praga_nome_cientifico")
    comum = reg.get("praga_nome_comum")
    candidatos = [p for p in pares_api if p["cultura_norm"] == cultura]

    if cientifico:
        alvo = normalizar(sem_autor(cientifico))
        if any(p["praga_cientifico_norm"] == alvo for p in candidatos):
            return "validado", saida
        return "manual_review", saida

    if comum:
        alvo = normalizar(comum)
        matches = {p["praga_cientifico_norm"]: p for p in candidatos if p["praga_comum_norm"] == alvo}
        if len(matches) == 1:  # único → enriquece o científico a partir da API
            saida["praga_nome_cientifico"] = next(iter(matches.values()))["praga_nome_cientifico"]
            return "validado", saida
        return "manual_review", saida  # zero ou ambíguo

    return "manual_review", saida  # sem nenhum nome de praga
```

- [ ] **Step 5: Rodar e ver passar** — `python -m pytest -q` → 20 passed.

- [ ] **Step 6: Commit**
```bash
git add extractor
git commit -m "feat: validação de registros extraídos + vocabulário de unidades"
```

---

### Task 8: Extractor — carga 2 (indicações), flags, estado.json, cobertura

**Files:**
- Modify: `extractor/import_db.py` (acrescentar), `extractor/tests/fixtures/` (novo fixture)
- Create: `extractor/tests/test_carga_extracted.py`, `extractor/tests/fixtures/extracted_6099.json`

**Interfaces:**
- Consumes: `conectar`, `carga_metadata` (Task 6), `validar_registro` (Task 7), `pre/`/`extracted/` (Tasks 5 e 9).
- Produces: `carga_extracted(conn, dir_extracted: Path, unidades: set[str]) -> dict` (resumo `{"produtos": int, "validados": int, "manual_review": int}`), `derivar_estado(dir_produtos, dir_bulas, dir_pre, dir_extracted, importados: set[str]) -> dict[str, str]`, `relatorio_cobertura(conn) -> dict` (`{"pares_api": int, "pares_com_dose": int, "cobertura": float}`), CLI `python import_db.py` que roda tudo e imprime o relatório. O MCP (Task 10) lê as flags que esta task grava.

- [ ] **Step 1: Fixture do extracted**

`extractor/tests/fixtures/extracted_6099.json` — contrato do 2b (Task 9):
```json
{
  "numero_registro": "6099",
  "registros": [
    {
      "cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
      "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
      "volume_calda_min": 1000, "volume_calda_max": 1200, "volume_calda_unidade": "L/ha",
      "num_max_aplicacoes": null, "intervalo_aplicacao": "7 a 15 dias",
      "carencia_dias": 7, "carencia_texto": null,
      "epoca_aplicacao": "preventivo", "fonte_pagina": 4,
      "fonte_trecho": "UVA | Oídio | Uncinula necator | - | 30 | 1000 - 1200"
    },
    {
      "cultura": "Uva", "praga_nome_comum": "Ferrugem", "praga_nome_cientifico": "Phakopsora euvitis",
      "dose_min": 0, "dose_max": 50, "dose_unidade": "mL/100L",
      "volume_calda_min": null, "volume_calda_max": null, "volume_calda_unidade": null,
      "num_max_aplicacoes": null, "intervalo_aplicacao": null,
      "carencia_dias": null, "carencia_texto": "UNA",
      "epoca_aplicacao": null, "fonte_pagina": 4, "fonte_trecho": "UVA | Ferrugem | 50"
    }
  ]
}
```
(O 2º registro tem `dose_min: 0` de propósito → reprova → `manual_review`.)

- [ ] **Step 2: Teste que falha**

`extractor/tests/test_carga_extracted.py`:
```python
import json
import shutil
from pathlib import Path

from import_db import carga_extracted, carga_metadata, conectar, derivar_estado, relatorio_cobertura

FIXTURES = Path(__file__).parent / "fixtures"
UNIDADES = set(json.loads((Path(__file__).parent.parent / "unidades.json").read_text()))


def preparar(tmp_path):
    for d in ("produtos", "bulas", "pre", "extracted"):
        (tmp_path / d).mkdir()
    shutil.copy(FIXTURES / "produto_6099.json", tmp_path / "produtos" / "6099.json")
    (tmp_path / "bulas" / "6099.pdf").write_bytes(b"%PDF")
    shutil.copy(FIXTURES / "extracted_6099.json", tmp_path / "extracted" / "6099.json")
    conn = conectar(tmp_path / "doses.db")
    carga_metadata(conn, tmp_path / "produtos", tmp_path / "bulas")
    return conn, tmp_path


def test_import_parcial_valido_entra_reprovado_marca_review(tmp_path):
    conn, _ = preparar(tmp_path)
    resumo = carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    assert resumo == {"produtos": 1, "validados": 1, "manual_review": 1}

    linhas = conn.execute("SELECT praga_comum_norm, status FROM indicacoes ORDER BY status").fetchall()
    assert [(l["praga_comum_norm"], l["status"]) for l in linhas] == [
        ("ferrugem", "manual_review"), ("oidio", "validado"),
    ]


def test_flags_processada_e_incompleto(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    prod = conn.execute("SELECT processada, incompleto FROM produtos").fetchone()
    assert prod["processada"] == 1
    # pares da API: uva/oidio (validado), uva/ferrugem (só manual_review),
    # algodao/ramularia (sem registro) → incompleto
    assert prod["incompleto"] == 1


def test_reimport_idempotente(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    assert conn.execute("SELECT COUNT(*) c FROM indicacoes").fetchone()["c"] == 2


def test_cobertura(tmp_path):
    conn, _ = preparar(tmp_path)
    carga_extracted(conn, tmp_path / "extracted", UNIDADES)
    r = relatorio_cobertura(conn)
    assert r["pares_api"] == 3
    assert r["pares_com_dose"] == 1        # só uva/oidio tem dose validada
    assert abs(r["cobertura"] - 1 / 3) < 1e-9


def test_extracted_vazio_processada_sem_indicacoes(tmp_path):
    conn, base = preparar(tmp_path)
    (base / "extracted" / "6099.json").write_text(
        json.dumps({"numero_registro": "6099", "registros": [], "motivo": "bula sem tabela de dose"})
    )
    resumo = carga_extracted(conn, base / "extracted", UNIDADES)
    assert resumo["validados"] == 0
    assert conn.execute("SELECT processada FROM produtos").fetchone()["processada"] == 1


def test_derivar_estado_cascata(tmp_path):
    _, base = preparar(tmp_path)
    # 6099 tem extracted e foi importado; 7777 sem bula; 8888 com .scan; 9999 só pre
    shutil.copy(FIXTURES / "produto_6099.json", base / "produtos" / "7777.json")
    (base / "pre" / "8888.scan").write_bytes(b"")
    (base / "pre" / "9999.txt").write_text("=== PÁGINA 1 ===\nDOSE")
    estados = derivar_estado(base / "produtos", base / "bulas", base / "pre",
                             base / "extracted", importados={"6099"})
    assert estados["6099"] == "importada"
    assert estados["7777"] == "sem_bula"      # produto existe, bula não está em raw/bulas
    assert estados["8888"] == "manual_review"
    assert estados["9999"] == "pre_ok"


def test_estado_scan_superado_por_extracted(tmp_path):
    _, base = preparar(tmp_path)
    (base / "pre" / "6099.scan").write_bytes(b"")  # scan + extracted → extracted vence
    estados = derivar_estado(base / "produtos", base / "bulas", base / "pre",
                             base / "extracted", importados=set())
    assert estados["6099"] == "extraida"
```

- [ ] **Step 3: Rodar e ver falhar** — `python -m pytest tests/test_carga_extracted.py -q` → ImportError.

- [ ] **Step 4: Implementar** (acrescentar a `extractor/import_db.py`)

```python
# ── Carga 2: indicações extraídas ────────────────────────────────────────────

COLS_INDICACAO = [
    "produto_fk", "cultura", "cultura_norm",
    "praga_nome_cientifico", "praga_cientifico_norm", "praga_nome_comum", "praga_comum_norm",
    "dose_min", "dose_max", "dose_unidade",
    "volume_calda_min", "volume_calda_max", "volume_calda_unidade",
    "num_max_aplicacoes", "intervalo_aplicacao",
    "carencia_dias", "carencia_texto", "epoca_aplicacao",
    "fonte_pagina", "fonte_trecho", "status",
]


def _linha_indicacao(reg_produto: str, registro: dict, status: str) -> dict:
    cientifico = registro.get("praga_nome_cientifico")
    comum = registro.get("praga_nome_comum")
    linha = {c: registro.get(c) for c in COLS_INDICACAO if c not in
             ("produto_fk", "cultura_norm", "praga_cientifico_norm", "praga_comum_norm", "status")}
    linha.update({
        "produto_fk": reg_produto,
        "cultura_norm": normalizar(registro.get("cultura") or ""),
        "praga_cientifico_norm": normalizar(sem_autor(cientifico)) if cientifico else None,
        "praga_comum_norm": normalizar(comum) if comum else None,
        "status": status,
    })
    return linha


def _par_tem_dose(conn: sqlite3.Connection, produto: str, par: sqlite3.Row) -> bool:
    """Par da API coberto = existe indicação validada do produto casando por científico OU comum."""
    return conn.execute(
        "SELECT 1 FROM indicacoes WHERE produto_fk = ? AND cultura_norm = ? AND status = 'validado'"
        " AND (   (praga_cientifico_norm IS NOT NULL AND praga_cientifico_norm = ?)"
        "      OR (praga_comum_norm      IS NOT NULL AND praga_comum_norm      = ?))"
        " LIMIT 1",
        (produto, par["cultura_norm"], par["praga_cientifico_norm"], par["praga_comum_norm"]),
    ).fetchone() is not None


def carga_extracted(conn: sqlite3.Connection, dir_extracted: Path, unidades: set[str]) -> dict:
    from validacao import validar_registro

    resumo = {"produtos": 0, "validados": 0, "manual_review": 0}
    for arq in sorted(dir_extracted.glob("*.json")):
        dados = json.loads(arq.read_text(encoding="utf-8"))
        reg = dados["numero_registro"]
        pares_api = conn.execute(
            "SELECT cultura_norm, praga_cientifico_norm, praga_comum_norm, praga_nome_cientifico"
            " FROM indicacoes_api WHERE produto_fk = ?", (reg,)
        ).fetchall()

        conn.execute("DELETE FROM indicacoes WHERE produto_fk = ?", (reg,))
        for registro in dados.get("registros") or []:
            status, enriquecido = validar_registro(registro, unidades, pares_api)
            linha = _linha_indicacao(reg, enriquecido, status)
            cols = ", ".join(COLS_INDICACAO)
            marcadores = ", ".join(f":{c}" for c in COLS_INDICACAO)
            conn.execute(f"INSERT INTO indicacoes ({cols}) VALUES ({marcadores})", linha)
            resumo["validados" if status == "validado" else "manual_review"] += 1

        incompleto = any(not _par_tem_dose(conn, reg, par) for par in pares_api)
        conn.execute(
            "UPDATE produtos SET processada = 1, incompleto = ? WHERE numero_registro = ?",
            (1 if incompleto else 0, reg),
        )
        resumo["produtos"] += 1
    conn.commit()
    return resumo


# ── Estado do pipeline (derivado; ninguém escreve à mão) ─────────────────────

def derivar_estado(dir_produtos: Path, dir_bulas: Path, dir_pre: Path,
                   dir_extracted: Path, importados: set[str]) -> dict[str, str]:
    """Cascata do estado mais avançado para o mais básico — vale o primeiro que casar."""
    estados: dict[str, str] = {}
    for arq in sorted(dir_produtos.glob("*.json")):
        reg = arq.stem
        extracted = dir_extracted / f"{reg}.json"
        if reg in importados and extracted.exists():
            dados = json.loads(extracted.read_text(encoding="utf-8"))
            estados[reg] = "vazia" if not dados.get("registros") else "importada"
        elif extracted.exists():
            estados[reg] = "extraida"
        elif (dir_pre / f"{reg}.txt").exists():
            estados[reg] = "pre_ok"
        elif (dir_pre / f"{reg}.scan").exists():
            estados[reg] = "manual_review"
        elif not (dir_bulas / f"{reg}.pdf").exists():
            estados[reg] = "sem_bula"
        else:
            estados[reg] = "pendente"
    return estados


def relatorio_cobertura(conn: sqlite3.Connection) -> dict:
    """% dos pares da API (de produtos COM bula) cobertos por dose validada."""
    pares = conn.execute(
        "SELECT a.produto_fk, a.cultura_norm, a.praga_cientifico_norm, a.praga_comum_norm"
        " FROM indicacoes_api a JOIN produtos p ON p.numero_registro = a.produto_fk"
        " WHERE p.bula_arquivo IS NOT NULL"
    ).fetchall()
    com_dose = sum(1 for par in pares if _par_tem_dose(conn, par["produto_fk"], par))
    total = len(pares)
    return {"pares_api": total, "pares_com_dose": com_dose,
            "cobertura": (com_dose / total) if total else 0.0}


def main() -> None:
    unidades = set(json.loads((Path(__file__).resolve().parent / "unidades.json").read_text()))
    dir_dados = RAIZ / "data"
    dir_dados.mkdir(exist_ok=True)
    conn = conectar(dir_dados / "doses.db")

    n = carga_metadata(conn, RAIZ / "raw" / "produtos", RAIZ / "raw" / "bulas")
    print(f"carga 1: {n} produtos")

    resumo = carga_extracted(conn, RAIZ / "extracted", unidades)
    print(f"carga 2: {resumo}")

    importados = {a.stem for a in (RAIZ / "extracted").glob("*.json")}
    estados = derivar_estado(RAIZ / "raw" / "produtos", RAIZ / "raw" / "bulas",
                             RAIZ / "pre", RAIZ / "extracted", importados)
    (RAIZ / "estado.json").write_text(json.dumps(estados, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print("estados:", dict(Counter(estados.values())))

    cob = relatorio_cobertura(conn)
    print(f"cobertura: {cob['pares_com_dose']}/{cob['pares_api']} = {cob['cobertura']:.1%}"
          f" (aceite: >= 90%)")


if __name__ == "__main__":
    main()
```
(Nota: `carga_extracted` importa `validar_registro` dentro da função para evitar import circular futuro — os módulos são irmãos no mesmo diretório e o CLI roda de `extractor/`. `main()` cria `extracted/` vazio se não existir? Não — `RAIZ / "extracted"` deve existir; criar com `mkdir(exist_ok=True)` antes de usar, junto do `dir_dados`.)

Acrescentar em `main()` antes da carga 2: `(RAIZ / "extracted").mkdir(exist_ok=True)`.

- [ ] **Step 5: Rodar e ver passar** — `python -m pytest -q` → 27 passed.

- [ ] **Step 6: Smoke local** — `python import_db.py` com o que existir de `raw/` do smoke:
Expected: `carga 1: ~100 produtos`, `carga 2: {'produtos': 0, ...}` (extracted vazio ainda), `estados:` com `pendente`/`pre_ok`/`sem_bula`, cobertura 0%.

- [ ] **Step 7: Commit**
```bash
git add extractor
git commit -m "feat: carga 2, flags de qualidade, estado derivado e relatório de cobertura"
```

---

### Task 9: Extractor — EXTRACAO.md (procedimento do 2b)

**Files:**
- Create: `extractor/EXTRACAO.md`, diretório `extracted/` com `.gitkeep`

**Interfaces:**
- Consumes: formato `pre/<reg>.txt` (Task 5), contrato JSON (Tasks 7–8).
- Produces: o documento que qualquer sessão de Claude segue para gerar `extracted/<reg>.json` corretos. Verificação: o exemplo do documento é idêntico ao fixture `extracted_6099.json` que a Task 8 prova importável.

- [ ] **Step 1: Escrever o documento**

`extractor/EXTRACAO.md`:
````markdown
# Procedimento de extração (Bloco 2b)

Executor: Claude (Code), em lotes por sessão. Custo: subscription — nunca API paga.

## Regras inegociáveis
1. Transcreva, não interprete: todo número vem literalmente do `pre/<reg>.txt`.
   Dose ilegível, em prosa ambígua ou fora de tabela → NÃO chute: emita o
   registro com `dose_min`/`dose_max` como vieram (ou null) e deixe a validação
   reprovar para `manual_review`.
2. Um arquivo de saída por bula, SEMPRE — mesmo sem nenhum registro:
   `{"numero_registro": "<reg>", "registros": [], "motivo": "<por quê>"}`.
   Arquivo presente = bula processada (é a retomabilidade do pipeline).
3. Unidades exatamente como na bula, sem converter (mL/100L NUNCA vira L/ha).
   Grafia canônica do vocabulário `unidades.json` (ex.: `mL/100L`, `L/ha`).
4. Valor único → min = max. Faixa "30-50" → min=30, max=50.
5. `fonte_pagina` = número do marcador `=== PÁGINA N ===` de onde o dado saiu;
   `fonte_trecho` = linha da tabela/texto de origem (recortada, até ~120 chars).
6. Carência: número em `carencia_dias`; texto ("UNA", "Não determinado…") em
   `carencia_texto` com `carencia_dias: null`.

## Formato de saída (contrato com import_db.py)
```json
{
  "numero_registro": "6099",
  "registros": [
    {
      "cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
      "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
      "volume_calda_min": 1000, "volume_calda_max": 1200, "volume_calda_unidade": "L/ha",
      "num_max_aplicacoes": null, "intervalo_aplicacao": "7 a 15 dias",
      "carencia_dias": 7, "carencia_texto": null,
      "epoca_aplicacao": "preventivo", "fonte_pagina": 4,
      "fonte_trecho": "UVA | Oídio | Uncinula necator | - | 30 | 1000 - 1200"
    }
  ]
}
```
Campos desconhecidos = null. Um registro por (cultura, praga) — praga com nomes
comuns múltiplos na mesma linha da bula = um registro por nome comum só se as
doses diferirem; senão um registro com o primeiro nome.
Cultura agrupada na bula ("Citros", "todas as culturas com ocorrência do alvo")
→ um registro por cultura SÓ se a bula listar as culturas; senão um registro com
a cultura como está escrita (a validação manda para manual_review — correto).

## Procedimento por sessão (lote de ~40 bulas)
1. Escolher regs: arquivos em `pre/*.txt` sem correspondente em `extracted/`.
2. Para cada reg: ler `pre/<reg>.txt`, montar o JSON, gravar `extracted/<reg>.json`.
3. Ao final do lote: `cd extractor && python import_db.py` e conferir o
   relatório de cobertura + contagem de manual_review.
4. Commitar o lote: `git add extracted && git commit -m "data: lote extração <faixa>"`.

## Piloto (OBRIGATÓRIO antes do lote completo — spec, seção Testes)
1. Selecionar ~30 bulas estratificadas por titular (máx. 2 por fabricante):
   `python - <<'EOF'` com groupby de titular sobre `raw/produtos/*.json`.
2. Extrair as 30 conforme acima; para cada uma, conferir MANUALMENTE contra o
   PDF (humano abre o PDF, compara campo a campo) e registrar acertos/erros
   numa planilha `piloto.csv` (reg, campo, extraido, correto, ok?).
3. Metas: ≥95% de acurácia nos campos numéricos E ≤15% de taxa de manual_review
   E cobertura ≥90% nos pilotos. Abaixo → ajustar este documento (prompt) ou a
   heurística do preprocess → re-extrair as MESMAS 30 → re-medir.
4. Só liberar o lote completo com as três metas batidas.
````

- [ ] **Step 2: Verificar coerência com o fixture**

O bloco JSON de exemplo acima deve ser subconjunto exato de
`extractor/tests/fixtures/extracted_6099.json` (mesmos nomes de campos). Conferir com diff visual. Rodar `python -m pytest -q` — os testes da Task 8 são a prova de que o formato importa.

- [ ] **Step 3: Criar diretório versionado**
```bash
mkdir -p extracted && touch extracted/.gitkeep
```

- [ ] **Step 4: Commit**
```bash
git add extractor/EXTRACAO.md extracted/.gitkeep
git commit -m "docs: procedimento de extração 2b (contrato, lote, piloto)"
```

---

### Task 10: mcp-doses — scaffold + queries (4 casos + cobertura)

**Files:**
- Create: `mcp-doses/package.json`, `mcp-doses/tsconfig.json`, `mcp-doses/src/normalizar.ts`, `mcp-doses/src/queries.ts`, `mcp-doses/tests/queries.test.ts`

**Interfaces:**
- Consumes: schema da Task 6 (o teste cria o banco fixture executando o próprio `extractor/schema.sql`).
- Produces (para a Task 11):
```ts
type ResultadoBusca = {
  casos: Array<
    | { tipo: "dose"; numero_registro: string; marca: string; indicacoes: LinhaDose[];
        aviso_incompleto: boolean; bula_url: string | null }
    | { tipo: "sem_bula"; numero_registro: string; marca: string }
    | { tipo: "consulte_bula"; numero_registro: string; marca: string; bula_url: string | null }
  >;
  resumo_cobertura: { com_dose: number; autorizados: number } | null; // null quando filtrou por produto
};
buscarDose(db: Database, filtro: { cultura: string; praga?: string; produto?: string }): ResultadoBusca
detalharProduto(db: Database, numeroRegistro: string): object | null
listarCulturas(db: Database): string[]
listarPragas(db: Database, cultura: string): Array<{ nome_comum: string | null; nome_cientifico: string | null }>
normalizar(s: string): string   // espelho exato do normalizacao.py
```

- [ ] **Step 1: Scaffold**

`mcp-doses/package.json`:
```json
{
  "name": "mcp-doses",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "start": "tsx src/index.ts",
    "test": "node --import tsx --test tests/*.test.ts",
    "check": "tsc --noEmit"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.16.0",
    "better-sqlite3": "^11.5.0",
    "zod": "^3.25.76"
  },
  "devDependencies": {
    "@types/better-sqlite3": "^7.6.11",
    "@types/node": "^22.15.29",
    "tsx": "^4.19.0",
    "typescript": "^5.8.3"
  }
}
```
`mcp-doses/tsconfig.json`: igual ao de `coletor/tsconfig.json` (copiar).
Run: `cd mcp-doses && npm install`

- [ ] **Step 2: Teste que falha**

`mcp-doses/tests/queries.test.ts`:
```ts
import { test, before } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import Database from "better-sqlite3";
import { buscarDose, detalharProduto, listarCulturas, listarPragas } from "../src/queries.ts";
import { normalizar } from "../src/normalizar.ts";

let db: Database.Database;

function inserirProduto(reg: string, marca: string, opts: Partial<{
  bula_arquivo: string | null; processada: number; incompleto: number;
}> = {}) {
  db.prepare(
    `INSERT INTO produtos (numero_registro, marca_comercial, marca_norm, bula_arquivo, bula_url, processada, incompleto)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(reg, marca, normalizar(marca), opts.bula_arquivo ?? `${reg}.pdf`,
        `https://mapa/bula${reg}.pdf`, opts.processada ?? 1, opts.incompleto ?? 0);
}

function inserirParApi(reg: string, cultura: string, cientifico: string, comum: string) {
  db.prepare(
    `INSERT INTO indicacoes_api (produto_fk, cultura, cultura_norm, praga_nome_cientifico,
       praga_cientifico_norm, praga_nome_comum, praga_comum_norm)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(reg, cultura, normalizar(cultura), cientifico, normalizar(cientifico), comum, normalizar(comum));
}

function inserirIndicacao(reg: string, cultura: string, comum: string, status: string, dose = 30) {
  db.prepare(
    `INSERT INTO indicacoes (produto_fk, cultura, cultura_norm, praga_nome_comum, praga_comum_norm,
       dose_min, dose_max, dose_unidade, fonte_pagina, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, 'mL/100L', 4, ?)`
  ).run(reg, cultura, normalizar(cultura), comum, normalizar(comum), dose, dose, status);
}

before(() => {
  db = new Database(":memory:");
  db.exec(readFileSync(join(import.meta.dirname, "..", "..", "extractor", "schema.sql"), "utf8"));

  // caso 1: dose validada
  inserirProduto("1001", "ProdutoUm");
  inserirParApi("1001", "Uva", "Uncinula necator", "Oídio");
  inserirIndicacao("1001", "Uva", "Oídio", "validado");
  // caso 1 com aviso: dose validada + incompleto=1
  inserirProduto("1002", "ProdutoDois", { incompleto: 1 });
  inserirParApi("1002", "Uva", "Uncinula necator", "Oídio");
  inserirIndicacao("1002", "Uva", "Oídio", "validado");
  // caso 2: sem bula
  inserirProduto("2001", "SemBula", { bula_arquivo: null, processada: 0 });
  inserirParApi("2001", "Uva", "Uncinula necator", "Oídio");
  // caso 3a: não processada
  inserirProduto("3001", "NaoProcessada", { processada: 0 });
  inserirParApi("3001", "Uva", "Uncinula necator", "Oídio");
  // caso 3b: processada mas só manual_review para o filtro
  inserirProduto("3002", "SoReview");
  inserirParApi("3002", "Uva", "Uncinula necator", "Oídio");
  inserirIndicacao("3002", "Uva", "Oídio", "manual_review");
});

test("cultura+praga: classifica os 4 casos e resume cobertura", () => {
  const r = buscarDose(db, { cultura: "uva", praga: "oidio" });
  const porTipo = (t: string) => r.casos.filter(c => c.tipo === t).map(c => c.numero_registro);
  assert.deepEqual(porTipo("dose").sort(), ["1001", "1002"]);
  assert.deepEqual(porTipo("sem_bula"), ["2001"]);
  assert.deepEqual(porTipo("consulte_bula").sort(), ["3001", "3002"]);
  assert.deepEqual(r.resumo_cobertura, { com_dose: 2, autorizados: 5 });
});

test("dose validada com incompleto=1 sai como dose COM aviso (caso 3 não engole caso 1)", () => {
  const r = buscarDose(db, { cultura: "Uva", praga: "Oídio" });
  const c1002 = r.casos.find(c => c.numero_registro === "1002");
  assert.equal(c1002?.tipo, "dose");
  assert.equal((c1002 as { aviso_incompleto: boolean }).aviso_incompleto, true);
});

test("registro manual_review NUNCA sai como dose", () => {
  const r = buscarDose(db, { cultura: "Uva", praga: "Oídio" });
  for (const caso of r.casos.filter(c => c.tipo === "dose")) {
    for (const ind of (caso as { indicacoes: { status: string }[] }).indicacoes) {
      assert.equal(ind.status, "validado");
    }
  }
});

test("filtro por produto: resumo é null, matching por marca normalizada", () => {
  const r = buscarDose(db, { cultura: "Uva", produto: "produtouM" });
  assert.equal(r.resumo_cobertura, null);
  assert.equal(r.casos[0]?.numero_registro, "1001");
});

test("filtro por produto aceita numero_registro exato", () => {
  const r = buscarDose(db, { cultura: "Uva", produto: "3002" });
  assert.equal(r.casos[0]?.tipo, "consulte_bula");
});

test("praga casa também por nome científico", () => {
  const r = buscarDose(db, { cultura: "Uva", praga: "uncinula necator" });
  assert.ok(r.casos.some(c => c.numero_registro === "1001" && c.tipo === "dose"));
});

test("sem praga e sem produto: erro pedindo filtro", () => {
  assert.throws(() => buscarDose(db, { cultura: "Uva" }), /praga.*produto|produto.*praga/i);
});

test("listarPragas lê de indicacoes_api (praga não extraída continua visível)", () => {
  const pragas = listarPragas(db, "uva");
  assert.ok(pragas.some(p => p.nome_comum === "Oídio"));
});

test("listarCulturas e detalharProduto", () => {
  assert.deepEqual(listarCulturas(db), ["Uva"]);
  assert.equal((detalharProduto(db, "1001") as { marca_comercial: string }).marca_comercial, "ProdutoUm");
  assert.equal(detalharProduto(db, "9999"), null);
});
```

- [ ] **Step 3: Rodar e ver falhar** — `cd mcp-doses && npm test` → FAIL.

- [ ] **Step 4: Implementar**

`mcp-doses/src/normalizar.ts`:
```ts
/** Espelho exato de extractor/normalizacao.py — mudou lá, muda aqui. */
export function normalizar(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/\s+/g, " ");
}
```

`mcp-doses/src/queries.ts`:
```ts
import type { Database } from "better-sqlite3";
import { normalizar } from "./normalizar.ts";

export interface LinhaDose {
  cultura: string;
  praga_nome_comum: string | null;
  praga_nome_cientifico: string | null;
  dose_min: number; dose_max: number; dose_unidade: string;
  volume_calda_min: number | null; volume_calda_max: number | null; volume_calda_unidade: string | null;
  num_max_aplicacoes: number | null; intervalo_aplicacao: string | null;
  carencia_dias: number | null; carencia_texto: string | null;
  epoca_aplicacao: string | null;
  fonte_pagina: number | null; fonte_trecho: string | null;
  status: string;
}

type Caso =
  | { tipo: "dose"; numero_registro: string; marca: string; indicacoes: LinhaDose[];
      aviso_incompleto: boolean; bula_url: string | null }
  | { tipo: "sem_bula"; numero_registro: string; marca: string }
  | { tipo: "consulte_bula"; numero_registro: string; marca: string; bula_url: string | null };

export interface ResultadoBusca {
  casos: Caso[];
  resumo_cobertura: { com_dose: number; autorizados: number } | null;
}

interface ProdutoRow {
  numero_registro: string; marca_comercial: string; bula_arquivo: string | null;
  bula_url: string | null; processada: number; incompleto: number;
}

const FILTRO_PRAGA =
  " AND ((praga_cientifico_norm IS NOT NULL AND praga_cientifico_norm = @praga)" +
  "   OR (praga_comum_norm      IS NOT NULL AND praga_comum_norm      = @praga))";

export function buscarDose(
  db: Database,
  filtro: { cultura: string; praga?: string; produto?: string },
): ResultadoBusca {
  if (!filtro.praga && !filtro.produto) {
    throw new Error("Informe ao menos um filtro além da cultura: praga ou produto.");
  }
  const cultura = normalizar(filtro.cultura);
  const praga = filtro.praga ? normalizar(filtro.praga) : undefined;

  // universo: produtos autorizados para o filtro segundo a API (spec: indicacoes_api)
  let produtos: ProdutoRow[];
  if (filtro.produto) {
    const q = normalizar(filtro.produto);
    produtos = db.prepare(
      `SELECT DISTINCT p.* FROM produtos p JOIN indicacoes_api a ON a.produto_fk = p.numero_registro
       WHERE a.cultura_norm = @cultura
         AND (p.numero_registro = @bruto OR ';' || p.marca_norm || ';' LIKE '%;' || @q || ';%'
              OR p.marca_norm = @q)
       ${praga ? FILTRO_PRAGA.replaceAll("praga_", "a.praga_") : ""}`,
    ).all({ cultura, q, bruto: filtro.produto, praga }) as ProdutoRow[];
  } else {
    produtos = db.prepare(
      `SELECT DISTINCT p.* FROM produtos p JOIN indicacoes_api a ON a.produto_fk = p.numero_registro
       WHERE a.cultura_norm = @cultura ${FILTRO_PRAGA.replaceAll("praga_", "a.praga_")}`,
    ).all({ cultura, praga }) as ProdutoRow[];
  }

  const casos: Caso[] = [];
  for (const p of produtos) {
    const validadas = db.prepare(
      `SELECT * FROM indicacoes WHERE produto_fk = @reg AND cultura_norm = @cultura
         AND status = 'validado' ${praga ? FILTRO_PRAGA : ""}`,
    ).all({ reg: p.numero_registro, cultura, praga }) as LinhaDose[];

    if (validadas.length > 0) {
      casos.push({
        tipo: "dose", numero_registro: p.numero_registro, marca: p.marca_comercial,
        indicacoes: validadas, aviso_incompleto: p.incompleto === 1, bula_url: p.bula_url,
      });
    } else if (p.bula_arquivo === null) {
      casos.push({ tipo: "sem_bula", numero_registro: p.numero_registro, marca: p.marca_comercial });
    } else {
      casos.push({
        tipo: "consulte_bula", numero_registro: p.numero_registro,
        marca: p.marca_comercial, bula_url: p.bula_url,
      });
    }
  }

  const resumo = filtro.produto
    ? null
    : { com_dose: casos.filter(c => c.tipo === "dose").length, autorizados: casos.length };
  return { casos, resumo_cobertura: resumo };
}

export function detalharProduto(db: Database, numeroRegistro: string): object | null {
  const p = db.prepare("SELECT * FROM produtos WHERE numero_registro = ?").get(numeroRegistro);
  if (!p) return null;
  return {
    ...p,
    ingredientes: db.prepare("SELECT nome, grupo_quimico, concentracao, unidade FROM ingredientes_ativos WHERE produto_fk = ?").all(numeroRegistro),
    indicacoes: db.prepare("SELECT * FROM indicacoes WHERE produto_fk = ? AND status = 'validado'").all(numeroRegistro),
  };
}

export function listarCulturas(db: Database): string[] {
  return (db.prepare("SELECT DISTINCT cultura FROM indicacoes_api ORDER BY cultura").all() as { cultura: string }[])
    .map(r => r.cultura);
}

export function listarPragas(db: Database, cultura: string) {
  return db.prepare(
    `SELECT DISTINCT praga_nome_comum AS nome_comum, praga_nome_cientifico AS nome_cientifico
     FROM indicacoes_api WHERE cultura_norm = ? ORDER BY 1`,
  ).all(normalizar(cultura)) as Array<{ nome_comum: string | null; nome_cientifico: string | null }>;
}
```

- [ ] **Step 5: Rodar e ver passar** — `npm test` → 10 pass. `npm run check`.

- [ ] **Step 6: Commit**
```bash
git add mcp-doses
git commit -m "feat: mcp-doses queries — 4 casos, aviso de incompletude, resumo de cobertura"
```

---

### Task 11: mcp-doses — servidor MCP + README

**Files:**
- Create: `mcp-doses/src/index.ts`, `README.md` (raiz)
- Modify: `.bob/mcp.json` (registrar o novo servidor — manual, fora do git)

**Interfaces:**
- Consumes: `buscarDose`, `detalharProduto`, `listarCulturas`, `listarPragas` (Task 10); env `DOSES_DB` (caminho do banco; default `<raiz>/data/doses.db`).
- Produces: servidor MCP stdio com tools `buscar_dose`, `detalhar_produto`, `listar_culturas`, `listar_pragas`.

- [ ] **Step 1: Implementar o servidor** (padrão de `mcp-agrofit/src/index.ts` — registerTool + zod + stdio; textos em pt-BR)

`mcp-doses/src/index.ts`:
```ts
#!/usr/bin/env node
/**
 * MCP Doses — consulta de doses de bulas registradas no AgroFit/MAPA.
 * Consulta à bula registrada, NUNCA prescrição (Lei 7.802/89): toda resposta
 * referencia a bula de origem, e dose vem só de query no SQLite.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import Database from "better-sqlite3";
import { resolve } from "node:path";
import { z } from "zod";
import { buscarDose, detalharProduto, listarCulturas, listarPragas } from "./queries.ts";

const CAMINHO_DB = process.env.DOSES_DB ?? resolve(import.meta.dirname, "..", "..", "data", "doses.db");
const db = new Database(CAMINHO_DB, { readonly: true, fileMustExist: true });

const server = new McpServer({ name: "mcp-doses", version: "0.1.0" });

const AVISO_LEGAL =
  "Consulta à bula registrada no MAPA — não é recomendação. " +
  "Receituário agronômico é ato privativo de engenheiro agrônomo (Lei 7.802/89).";

function responder(dados: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify({ aviso: AVISO_LEGAL, ...(<object>dados) }, null, 1) }] };
}

function responderErro(err: unknown) {
  return {
    content: [{ type: "text" as const, text: `Erro: ${err instanceof Error ? err.message : String(err)}` }],
    isError: true,
  };
}

server.registerTool(
  "buscar_dose",
  {
    description:
      "Busca doses registradas em bula por cultura + (praga e/ou produto). " +
      "Responde 4 casos por produto: dose validada (com aviso se o produto tem lacunas), " +
      "sem bula disponível, consulte a bula original (não processada/incompleta), ou sem registro. " +
      "Em consulta por cultura+praga inclui resumo de cobertura X de Y.",
    inputSchema: z.object({
      cultura: z.string().describe("Nome da cultura (ex: 'Uva'). Obrigatório."),
      praga: z.string().optional().describe("Nome comum OU científico da praga (ex: 'Oídio')."),
      produto: z.string().optional().describe("Marca comercial ou número de registro Mapa."),
    }),
  },
  async ({ cultura, praga, produto }) => {
    try {
      return responder(buscarDose(db, { cultura, praga, produto }));
    } catch (err) {
      return responderErro(err);
    }
  },
);

server.registerTool(
  "detalhar_produto",
  {
    description: "Detalhes de um produto pelo número de registro Mapa: ingredientes, classificações e indicações validadas.",
    inputSchema: z.object({ numero_registro: z.string() }),
  },
  async ({ numero_registro }) => {
    try {
      const p = detalharProduto(db, numero_registro);
      return p ? responder(p) : responder({ resultado: "sem registro na base" });
    } catch (err) {
      return responderErro(err);
    }
  },
);

server.registerTool(
  "listar_culturas",
  { description: "Culturas com produtos autorizados na base.", inputSchema: z.object({}) },
  async () => {
    try {
      return responder({ culturas: listarCulturas(db) });
    } catch (err) {
      return responderErro(err);
    }
  },
);

server.registerTool(
  "listar_pragas",
  {
    description: "Pragas autorizadas pelo MAPA para uma cultura (universo da API, inclui as ainda não extraídas).",
    inputSchema: z.object({ cultura: z.string() }),
  },
  async ({ cultura }) => {
    try {
      return responder({ pragas: listarPragas(db, cultura) });
    } catch (err) {
      return responderErro(err);
    }
  },
);

async function main() {
  await server.connect(new StdioServerTransport());
  console.error(`[mcp-doses] rodando (db: ${CAMINHO_DB})`);
}

main().catch(err => {
  console.error("[mcp-doses] Erro fatal:", err);
  process.exit(1);
});
```

- [ ] **Step 2: Typecheck + testes** — `npm run check && npm test` → verdes.

- [ ] **Step 3: Smoke manual** — com o `data/doses.db` do smoke da Task 8:

Run: `cd mcp-doses && npm start` (deve logar `[mcp-doses] rodando`; Ctrl+C).
Registrar em `.bob/mcp.json` (adicionar ao objeto `mcpServers`, sem tocar no `agrofit`):
```json
"doses": { "command": "npx", "args": ["tsx", "D:\\Pragas Uva\\mcp-doses\\src\\index.ts"] }
```

- [ ] **Step 4: README da raiz**

`README.md` — visão geral honesta (o que é: consulta à bula registrada; o que NÃO é: prescrição), diagrama dos 3 blocos (copiar da spec), como rodar cada bloco (`npm run collect`, `python preprocess.py`, extração via `extractor/EXTRACAO.md`, `python import_db.py`, MCP), aviso Lei 7.802/89, e crédito às fontes (AgroFit/MAPA, API Embrapa).

- [ ] **Step 5: Commit**
```bash
git add mcp-doses README.md
git commit -m "feat: servidor MCP de doses + README"
```

---

### Task 12: Operação — coleta completa, pré-proc e preparação do piloto

Sem código novo — execução dos blocos prontos, com checkpoints. **Não** iniciar extração em massa: o piloto (EXTRACAO.md) vem primeiro e depende de revisão humana.

- [ ] **Step 1: Coleta completa (rede, ~2-4 h — rodar e deixar):**
```bash
cd coletor && npm run collect
```
Checkpoint: `produtos locais == X-Records-Count` (re-rodar se menor — é retomável); `raw/failures.jsonl` só com falhas pontuais; `ls raw/bulas | wc -l` ≈ 94% dos produtos.

- [ ] **Step 2: Re-tentar falhas de download** — re-rodar `npm run collect` (pula o que existe, re-tenta o que falta). Falha persistente fica registrada e o produto seguirá `sem_bula`/`pendente` — correto.

- [ ] **Step 3: Pré-processar tudo:**
```bash
cd extractor && python preprocess.py
```
Checkpoint: contagem de `.scan` (esperado: minoria); amostrar 3 `pre/*.txt` e conferir que a tabela de dose sobreviveu.

- [ ] **Step 4: Primeira carga:**
```bash
python import_db.py
```
Checkpoint: `carga 1: ~4252 produtos`; estados coerentes (`pre_ok` dominante, `sem_bula` ~6%).

- [ ] **Step 5: Selecionar as ~30 bulas do piloto** (estratificado, máx. 2 por titular) e listá-las em `extractor/piloto.txt`. A partir daqui o fluxo é o de `EXTRACAO.md` — extração em sessão com revisão humana campo a campo.

- [ ] **Step 6: Commit final de infra:**
```bash
git add extractor/piloto.txt
git commit -m "chore: coleta completa + pré-proc + seleção do piloto"
```

---

## Self-review (do plano, contra a spec)

- **Cobertura da spec:** Bloco 1 → Tasks 1–3 (retomável, multi_bula, failures, magic bytes, UA, token). 2a → Task 5 (keywords, adjacência, .scan, sem sufixo). 2b → Task 9 (contrato + piloto + metas). 2c → Tasks 6–8 (duas cargas, INSERT/UPDATE-metadata, apaga-e-regrava, validações com destino, inversa, flags, estado derivado em cascata, cobertura ≥90% impressa no CLI). Bloco 3 → Tasks 10–11 (4 casos, aviso incompleto, filtro validado, resumo X/Y, listagens em indicacoes_api, aviso legal). Testes da spec → cada task tem os seus; fixtures cobrem os 4 casos + 3 gatilhos do caso 3.
- **Sem placeholders:** todo step de código tem o código; nenhum "TBD"/"similar à task N".
- **Consistência de tipos:** `bulasDe`/`nomeArquivoBula` (T1) usados em T3; `criarClienteApi` (T2) em T3; `normalizar`/`sem_autor` (T4) em T5–8; `conectar`/`carga_metadata` (T6) em T8; `validar_registro` (T7) em T8; schema (T6) no fixture de T10; `buscarDose` etc. (T10) em T11. Contrato JSON idêntico em T7, T8 (fixture) e T9 (doc).
