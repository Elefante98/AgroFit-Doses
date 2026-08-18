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
  const mensagem = err instanceof Error ? err.message : String(err);
  return {
    content: [{ type: "text" as const, text: JSON.stringify({ aviso: AVISO_LEGAL, erro: mensagem }, null, 1) }],
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
      limite: z.number().int().min(1).max(100).optional()
        .describe("Máximo de produtos na resposta (default 20). casos_omitidos informa o corte."),
    }),
  },
  async ({ cultura, praga, produto, limite }) => {
    try {
      const r = buscarDose(db, { cultura, praga, produto, limite });
      // caso 4 explícito — o LLM cliente não deve interpretar vazio sozinho
      return responder(r.casos.length === 0 ? { resultado: "sem registro na base", ...r } : r);
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
