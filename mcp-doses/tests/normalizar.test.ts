import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizar, semAutor } from "../src/normalizar.ts";

// Espelho de extractor/tests/test_normalizacao.py — paridade Python <-> TS é invariante da spec.

test("normalizar: caixa, acento, espaços", () => {
  assert.equal(normalizar("  Oídio "), "oidio");
  assert.equal(normalizar("CANA-DE-AÇÚCAR"), "cana-de-acucar");
  assert.equal(normalizar("Uva  de   mesa"), "uva de mesa");
});

test("normalizar: vazio", () => {
  assert.equal(normalizar(""), "");
});

test("semAutor: remove parêntese final", () => {
  assert.equal(semAutor("Ageratum conyzoides (L.)"), "Ageratum conyzoides");
  assert.equal(semAutor("Uncinula necator"), "Uncinula necator");
});

test("semAutor: não remove parêntese no meio", () => {
  // parêntese interno (subgênero) não é autor — só o final sai
  assert.equal(semAutor("Praga (Sub) nome (Autor, 1900)"), "Praga (Sub) nome");
});
