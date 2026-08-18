import { appendFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import dotenv from "dotenv";
import { criarClienteApi } from "./api.ts";
import { bulasDe, nomeArquivoBula, type ProdutoResumo } from "./helpers.ts";
import { baixarPdf } from "./download.ts";

const RAIZ = resolve(import.meta.dirname, "..", "..");
dotenv.config({ path: join(RAIZ, ".env") });
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
    const algumaFaltando = bulas.some(
      (_, i) => !existsSync(join(DIR_BULAS, nomeArquivoBula(produto.numero_registro, i))),
    );
    if (bulas.length > 1 && algumaFaltando) {
      // loga só enquanto há download pendente — re-runs não acumulam duplicatas
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
