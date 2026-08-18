import type Database from "better-sqlite3";
import { normalizar, semAutor } from "./normalizar.ts";

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
  confirmacao: "bula+api" | "somente_bula";  // proveniência por linha
}

type Caso =
  | { tipo: "dose"; numero_registro: string; marca: string; indicacoes: LinhaDose[];
      aviso_incompleto: boolean; bula_arquivo: string | null; bula_url: string | null }
  | { tipo: "sem_bula"; numero_registro: string; marca: string; bula_url: string | null }
  | { tipo: "consulte_bula"; numero_registro: string; marca: string;
      bula_arquivo: string | null; bula_url: string | null };

export interface ResultadoBusca {
  casos: Caso[];
  casos_omitidos: number;   // truncados pelo limite — o resumo cobre o total
  resumo_cobertura: { com_dose: number; autorizados: number } | null;
}

const LIMITE_PADRAO = 20;
const ORDEM_TIPO: Record<Caso["tipo"], number> = { dose: 0, consulte_bula: 1, sem_bula: 2 };

interface ProdutoRow {
  numero_registro: string; marca_comercial: string; bula_arquivo: string | null;
  bula_url: string | null; processada: number; incompleto: number;
}

const FILTRO_PRAGA =
  " AND ((praga_cientifico_norm IS NOT NULL AND praga_cientifico_norm = @praga)" +
  "   OR (praga_comum_norm      IS NOT NULL AND praga_comum_norm      = @praga))";

export function buscarDose(
  db: Database.Database,
  filtro: { cultura: string; praga?: string; produto?: string; limite?: number },
): ResultadoBusca {
  if (!filtro.praga && !filtro.produto) {
    throw new Error("Informe ao menos um filtro além da cultura: praga ou produto.");
  }
  const cultura = normalizar(filtro.cultura);
  // semAutor: consulta com científico + autor ("Uncinula necator (Schwein.)") deve casar
  // o banco, que guarda o norm já sem autor (2c). Inócuo para nomes comuns.
  const praga = filtro.praga ? normalizar(semAutor(filtro.praga)) : undefined;

  // universo: produtos autorizados para o filtro segundo a API (spec: indicacoes_api)
  // better-sqlite3 rejeita chave de binding sem @param correspondente (e valor
  // undefined) — o objeto de binding é montado só com o que o SQL usa.
  let produtos: ProdutoRow[];
  if (filtro.produto) {
    const q = normalizar(filtro.produto);
    produtos = db.prepare(
      `SELECT DISTINCT p.* FROM produtos p JOIN indicacoes_api a ON a.produto_fk = p.numero_registro
       WHERE a.cultura_norm = @cultura
         AND (p.numero_registro = @bruto OR ';' || p.marca_norm || ';' LIKE '%;' || @q || ';%'
              OR p.marca_norm = @q)
       ${praga ? FILTRO_PRAGA.replaceAll("praga_", "a.praga_") : ""}`,
    ).all(praga
      ? { cultura, q, bruto: filtro.produto, praga }
      : { cultura, q, bruto: filtro.produto }) as ProdutoRow[];
  } else {
    produtos = db.prepare(
      `SELECT DISTINCT p.* FROM produtos p JOIN indicacoes_api a ON a.produto_fk = p.numero_registro
       WHERE a.cultura_norm = @cultura ${FILTRO_PRAGA.replaceAll("praga_", "a.praga_")}`,
    ).all({ cultura, praga }) as ProdutoRow[];
  }

  const casos: Caso[] = [];
  for (const p of produtos) {
    // decisão 2026-08-18: a bula é o documento registrado — validado_bula é
    // servido, com a proveniência explícita por linha (confirmacao)
    const validadas = (db.prepare(
      `SELECT * FROM indicacoes WHERE produto_fk = @reg AND cultura_norm = @cultura
         AND status IN ('validado', 'validado_bula') ${praga ? FILTRO_PRAGA : ""}`,
    ).all(praga
      ? { reg: p.numero_registro, cultura, praga }
      : { reg: p.numero_registro, cultura }) as LinhaDose[])
      .map(l => ({ ...l, confirmacao: (l.status === "validado" ? "bula+api" : "somente_bula") as LinhaDose["confirmacao"] }));

    if (validadas.length > 0) {
      casos.push({
        tipo: "dose", numero_registro: p.numero_registro, marca: p.marca_comercial,
        indicacoes: validadas, aviso_incompleto: p.incompleto === 1,
        bula_arquivo: p.bula_arquivo, bula_url: p.bula_url,
      });
    } else if (p.bula_arquivo === null) {
      casos.push({
        tipo: "sem_bula", numero_registro: p.numero_registro, marca: p.marca_comercial,
        bula_url: p.bula_url,
      });
    } else {
      casos.push({
        tipo: "consulte_bula", numero_registro: p.numero_registro,
        marca: p.marca_comercial, bula_arquivo: p.bula_arquivo, bula_url: p.bula_url,
      });
    }
  }

  const resumo = filtro.produto
    ? null
    : { com_dose: casos.filter(c => c.tipo === "dose").length, autorizados: casos.length };

  // teto de resposta: consultas amplas reais retornam 300+ produtos (~100 KB) e
  // estouram o contexto do cliente — trunca os casos, nunca o resumo
  casos.sort((a, b) =>
    ORDEM_TIPO[a.tipo] - ORDEM_TIPO[b.tipo] || a.numero_registro.localeCompare(b.numero_registro));
  const limite = filtro.limite ?? LIMITE_PADRAO;
  const exibidos = casos.slice(0, limite);
  return { casos: exibidos, casos_omitidos: casos.length - exibidos.length, resumo_cobertura: resumo };
}

export function detalharProduto(db: Database.Database, numeroRegistro: string): object | null {
  const p = db.prepare("SELECT * FROM produtos WHERE numero_registro = ?").get(numeroRegistro);
  if (!p) return null;
  return {
    ...p,
    ingredientes: db.prepare("SELECT nome, grupo_quimico, concentracao, unidade FROM ingredientes_ativos WHERE produto_fk = ?").all(numeroRegistro),
    indicacoes: db.prepare("SELECT * FROM indicacoes WHERE produto_fk = ? AND status = 'validado'").all(numeroRegistro),
  };
}

export function listarCulturas(db: Database.Database): string[] {
  return (db.prepare("SELECT DISTINCT cultura FROM indicacoes_api ORDER BY cultura").all() as { cultura: string }[])
    .map(r => r.cultura);
}

export function listarPragas(db: Database.Database, cultura: string) {
  return db.prepare(
    `SELECT DISTINCT praga_nome_comum AS nome_comum, praga_nome_cientifico AS nome_cientifico
     FROM indicacoes_api WHERE cultura_norm = ? ORDER BY 1`,
  ).all(normalizar(cultura)) as Array<{ nome_comum: string | null; nome_cientifico: string | null }>;
}
