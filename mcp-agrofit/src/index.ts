#!/usr/bin/env node
/**
 * MCP Server – Agrofit/Embrapa
 *
 * Exposes tools to query the Agrofit API:
 *   - search_products   → busca produtos formulados por cultura e/ou praga
 *   - get_product       → detalha um produto pelo número de registro
 *   - list_pests        → lista pragas de uma cultura
 *   - list_cultures     → lista culturas disponíveis
 *   - list_active_ingredients → lista ingredientes ativos
 *
 * Auth: OAuth2 client_credentials (Embrapa API Store)
 * Env vars required: CONSUMER_KEY, CONSUMER_SECRET
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// ─── Config ──────────────────────────────────────────────────────────────────

const CONSUMER_KEY = process.env.CONSUMER_KEY;
const CONSUMER_SECRET = process.env.CONSUMER_SECRET;

if (!CONSUMER_KEY || !CONSUMER_SECRET) {
  console.error(
    "[agrofit] CONSUMER_KEY and CONSUMER_SECRET env vars are required."
  );
  process.exit(1);
}

const TOKEN_URL = "https://api.cnptia.embrapa.br/token";
const BASE_URL = "https://api.cnptia.embrapa.br/agrofit/v1";

// ─── Token cache ──────────────────────────────────────────────────────────────

let cachedToken: string | null = null;
let tokenExpiresAt = 0;

async function getToken(): Promise<string> {
  // Reuse token if it still has >60 s of lifetime left
  if (cachedToken && Date.now() < tokenExpiresAt - 60_000) {
    return cachedToken;
  }

  const basic = Buffer.from(`${CONSUMER_KEY}:${CONSUMER_SECRET}`).toString(
    "base64"
  );

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Token request failed (${res.status}): ${body}`);
  }

  const json = (await res.json()) as { access_token: string; expires_in?: number };
  cachedToken = json.access_token;
  // expires_in is in seconds; default to 3600 if not provided
  tokenExpiresAt = Date.now() + (json.expires_in ?? 3600) * 1000;
  return cachedToken;
}

// ─── Shared fetch helper ──────────────────────────────────────────────────────

async function agrofitGet(
  path: string,
  params: Record<string, string | number | undefined>
): Promise<unknown> {
  const token = await getToken();

  // Build query string, skipping undefined values
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }

  const url = `${BASE_URL}${path}${qs.size ? "?" + qs.toString() : ""}`;

  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Agrofit API error (${res.status}) for ${path}: ${body}`);
  }

  return res.json();
}

// ─── MCP Server ───────────────────────────────────────────────────────────────

const server = new McpServer({ name: "mcp-agrofit", version: "0.1.0" });

// ── Tool 1: search_products ───────────────────────────────────────────────────
server.registerTool(
  "search_products",
  {
    description:
      "Busca produtos fitossanitários registrados na Agrofit para uma determinada cultura e/ou praga. " +
      "Retorna lista de produtos com número de registro, nome comercial, ingrediente ativo e empresa. " +
      "Use para responder perguntas como 'Quais produtos combatem Oídio em videira?'",
    inputSchema: z.object({
      cultura: z
        .string()
        .optional()
        .describe(
          "Nome da cultura (ex: 'Uva', 'Uva de mesa'). Deixe vazio para não filtrar por cultura."
        ),
      praga_nome_comum: z
        .string()
        .optional()
        .describe(
          "Nome comum da praga (ex: 'Oídio', 'Tripes', 'Cochonilha'). Deixe vazio para não filtrar por praga."
        ),
      ingrediente_ativo: z
        .string()
        .optional()
        .describe("Filtrar por ingrediente ativo (ex: 'azoxistrobina')."),
      page: z
        .number()
        .int()
        .min(1)
        .optional()
        .default(1)
        .describe("Página de resultados (começa em 1)."),
    }),
  },
  async ({ cultura, praga_nome_comum, ingrediente_ativo, page }) => {
    try {
      const data = await agrofitGet("/search/produtos-formulados", {
        cultura,
        praga_nome_comum,
        ingrediente_ativo,
        page,
      });
      return {
        content: [
          { type: "text", text: JSON.stringify(data, null, 2) },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Erro ao buscar produtos: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// ── Tool 2: get_product ───────────────────────────────────────────────────────
server.registerTool(
  "get_product",
  {
    description:
      "Retorna os detalhes completos de um produto fitossanitário pelo seu número de registro no Mapa. " +
      "Inclui ingrediente ativo, formulação, prazo de carência, classe toxicológica e empresa titular.",
    inputSchema: z.object({
      numero_registro: z
        .string()
        .describe("Número de registro do produto no Mapa (ex: '0001820')."),
    }),
  },
  async ({ numero_registro }) => {
    try {
      const data = await agrofitGet(
        `/produtos-formulados/${encodeURIComponent(numero_registro)}`,
        {}
      );
      return {
        content: [
          { type: "text", text: JSON.stringify(data, null, 2) },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Erro ao buscar produto ${numero_registro}: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// ── Tool 3: list_pests ────────────────────────────────────────────────────────
server.registerTool(
  "list_pests",
  {
    description:
      "Lista as pragas (doenças, insetos, plantas daninhas) registradas na Agrofit, " +
      "com opção de filtrar pelo nome da cultura. " +
      "Útil para descobrir quais pragas afetam videira/uva.",
    inputSchema: z.object({
      cultura: z
        .string()
        .optional()
        .describe("Nome da cultura para filtrar pragas (ex: 'Uva')."),
      page: z
        .number()
        .int()
        .min(1)
        .optional()
        .default(1)
        .describe("Página de resultados."),
    }),
  },
  async ({ cultura, page }) => {
    try {
      const data = await agrofitGet("/pragas", { cultura, page });
      return {
        content: [
          { type: "text", text: JSON.stringify(data, null, 2) },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Erro ao listar pragas: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// ── Tool 4: list_cultures ─────────────────────────────────────────────────────
server.registerTool(
  "list_cultures",
  {
    description:
      "Lista todas as culturas agrícolas disponíveis na Agrofit. " +
      "Use para descobrir os nomes exatos de cultura antes de chamar search_products ou list_pests.",
    inputSchema: z.object({
      page: z
        .number()
        .int()
        .min(1)
        .optional()
        .default(1)
        .describe("Página de resultados."),
    }),
  },
  async ({ page }) => {
    try {
      const data = await agrofitGet("/culturas", { page });
      return {
        content: [
          { type: "text", text: JSON.stringify(data, null, 2) },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Erro ao listar culturas: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// ── Tool 5: list_active_ingredients ──────────────────────────────────────────
server.registerTool(
  "list_active_ingredients",
  {
    description:
      "Lista os ingredientes ativos (princípios ativos) cadastrados na Agrofit. " +
      "Útil para saber os nomes técnicos antes de filtrar produtos por ingrediente ativo.",
    inputSchema: z.object({
      nome: z
        .string()
        .optional()
        .describe("Filtrar por nome do ingrediente ativo (busca parcial)."),
      page: z
        .number()
        .int()
        .min(1)
        .optional()
        .default(1)
        .describe("Página de resultados."),
    }),
  },
  async ({ nome, page }) => {
    try {
      const data = await agrofitGet("/ingredientes-ativos", { nome, page });
      return {
        content: [
          { type: "text", text: JSON.stringify(data, null, 2) },
        ],
      };
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Erro ao listar ingredientes ativos: ${err instanceof Error ? err.message : String(err)}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// ─── Bootstrap ────────────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[agrofit] MCP server running on stdio");
}

main().catch((err) => {
  console.error("[agrofit] Fatal error:", err);
  process.exit(1);
});
