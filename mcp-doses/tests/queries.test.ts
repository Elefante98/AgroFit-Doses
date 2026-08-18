import { test, before } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import Database from "better-sqlite3";
import { buscarDose, detalharProduto, listarCulturas, listarPragas } from "../src/queries.ts";
import { normalizar } from "../src/normalizar.ts";

let db: Database.Database;

function inserirProduto(reg: string, marca: string, opts: Partial<{
  bula_arquivo: string | null; processada: number; incompleto: number; marca_norm: string;
}> = {}) {
  // "in" e não "??": o caso 2 passa bula_arquivo null DE PROPÓSITO — ?? o engoliria
  const bula = "bula_arquivo" in opts ? opts.bula_arquivo : `${reg}.pdf`;
  db.prepare(
    `INSERT INTO produtos (numero_registro, marca_comercial, marca_norm, bula_arquivo, bula_url, processada, incompleto)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(reg, marca, opts.marca_norm ?? normalizar(marca), bula,
        `https://mapa/bula${reg}.pdf`, opts.processada ?? 1, opts.incompleto ?? 0);
}

function inserirParApi(reg: string, cultura: string, cientifico: string, comum: string) {
  db.prepare(
    `INSERT INTO indicacoes_api (produto_fk, cultura, cultura_norm, praga_nome_cientifico,
       praga_cientifico_norm, praga_nome_comum, praga_comum_norm)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).run(reg, cultura, normalizar(cultura), cientifico, normalizar(cientifico), comum, normalizar(comum));
}

function inserirIndicacao(reg: string, cultura: string, comum: string, status: string,
                          dose = 30, cientifico = "Uncinula necator") {
  db.prepare(
    `INSERT INTO indicacoes (produto_fk, cultura, cultura_norm, praga_nome_comum, praga_comum_norm,
       praga_nome_cientifico, praga_cientifico_norm,
       dose_min, dose_max, dose_unidade, fonte_pagina, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'mL/100L', 4, ?)`
  ).run(reg, cultura, normalizar(cultura), comum, normalizar(comum),
        cientifico, normalizar(cientifico), dose, dose, status);
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
  // multi-marca: pina o separador ";" sem espaço (regressão para "; " quebra a 2ª marca)
  inserirProduto("4001", "Marca Um; Marca Dois", { marca_norm: "marca um;marca dois" });
  inserirParApi("4001", "Uva", "Uncinula necator", "Oídio");
  inserirIndicacao("4001", "Uva", "Oídio", "validado");
});

test("cultura+praga: classifica os 4 casos e resume cobertura", () => {
  const r = buscarDose(db, { cultura: "uva", praga: "oidio" });
  const porTipo = (t: string) => r.casos.filter(c => c.tipo === t).map(c => c.numero_registro);
  assert.deepEqual(porTipo("dose").sort(), ["1001", "1002", "4001"]);
  assert.deepEqual(porTipo("sem_bula"), ["2001"]);
  assert.deepEqual(porTipo("consulte_bula").sort(), ["3001", "3002"]);
  assert.deepEqual(r.resumo_cobertura, { com_dose: 3, autorizados: 6 });
});

test("caso 2 (sem_bula) inclui bula_url mesmo com bula_arquivo null (download falhou/formato .doc)", () => {
  const r = buscarDose(db, { cultura: "Uva", praga: "Oídio" });
  const semBula = r.casos.find(c => c.numero_registro === "2001");
  assert.equal(semBula?.tipo, "sem_bula");
  assert.equal((semBula as { bula_url: string | null }).bula_url, "https://mapa/bula2001.pdf");
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

test("produto multi-marca é encontrado pela SEGUNDA marca", () => {
  const r = buscarDose(db, { cultura: "Uva", produto: "marca dois" });
  assert.equal(r.casos[0]?.numero_registro, "4001");
});

test("praga casa também por nome científico", () => {
  const r = buscarDose(db, { cultura: "Uva", praga: "uncinula necator" });
  assert.ok(r.casos.some(c => c.numero_registro === "1001" && c.tipo === "dose"));
});

test("sem praga e sem produto: erro pedindo filtro", () => {
  assert.throws(() => buscarDose(db, { cultura: "Uva" }), /praga.*produto|produto.*praga/i);
});

test("caso 4: filtro que não casa nada retorna casos vazios (sem registro na base)", () => {
  const r = buscarDose(db, { cultura: "Tomate", praga: "Traça" });
  assert.deepEqual(r.casos, []);
  assert.deepEqual(r.resumo_cobertura, { com_dose: 0, autorizados: 0 });
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
