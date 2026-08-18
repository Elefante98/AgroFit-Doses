CREATE TABLE IF NOT EXISTS produtos (
  numero_registro TEXT PRIMARY KEY,
  marca_comercial TEXT,            -- lista da API unida com "; " (exibição)
  marca_norm      TEXT,            -- marcas normalizadas unidas com ";" SEM espaço (match)
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
