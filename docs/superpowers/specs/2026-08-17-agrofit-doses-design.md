# AgroFit Doses — Design

**Data:** 2026-08-17
**Status:** Aprovado (abordagem C)

## Objetivo

Construir um banco local estruturado de doses de defensivos agrícolas por
(produto, cultura, praga), extraído das bulas em PDF registradas no AgroFit/MAPA —
dado que a API do AgroFit não fornece. Expor via MCP para consulta de agrônomos.

**Posicionamento:** ferramenta de *consulta à bula registrada* ("o que o MAPA
autoriza"), nunca prescrição. Recomendação de dose é ato privativo de engenheiro
agrônomo (Lei 7.802/89) — toda resposta referencia a bula de origem.

**Motivação secundária:** aprendizado + exposição no LinkedIn (2 posts: dataset+MCP;
depois agente local). Futuro possível: alimentar o FrutiT.

## Escopo

- Todas as culturas do AgroFit: **4.252 produtos formulados**, ~94% com bula em PDF.
- Fora de escopo (por ora): agente standalone com modelo local (fase B posterior),
  integração FrutiT, atualização automática periódica.

## Arquitetura — 3 blocos

```
[API AgroFit] ──► Bloco 1: Coletor ──► raw/ (JSON + PDFs)
                                          │
                  Bloco 2: Extração ◄─────┘  (Claude, via subscription, em lotes)
                       │
                       ▼
                  SQLite (doses.db)
                       │
                  Bloco 3: MCP server ──► cliente (Claude / Ollama futuro)
```

### Bloco 1 — Coletor (script Node/TS, sem IA)

- Pagina `GET /produtos-formulados` (43 páginas × 100) e salva um JSON por produto
  em `raw/produtos/<numero_registro>.json`.
- Baixa o PDF de cada documento `tipo_documento == "Bula"` para
  `raw/bulas/<numero_registro>.pdf`.
- Requisitos: retomável (pula o que já existe), rate-limit educado (~1 req/s),
  `--http1.1` + User-Agent de navegador (o servidor do MAPA rejeita curl puro),
  log de falhas em `raw/failures.jsonl` para retry.
- Token OAuth2 renovado automaticamente (expira ~25 min).

### Bloco 2 — Extração (Claude Code, subscription, sem custo de API)

- Pré-processamento por script: `pdfplumber` extrai texto + tabelas de cada bula;
  só as seções relevantes (~25% do texto) vão para o contexto de extração.
- Claude transforma cada bula em registros com schema fixo (abaixo), em lotes por
  sessão. Bulas com layout impossível → fila `manual_review`.
- Cada registro carrega proveniência: arquivo da bula, página, trecho de origem.
- Validação automática pós-extração: dose numérica > 0, unidade num vocabulário
  controlado, (cultura, praga) existente no `indicacao_uso` da API — divergências
  vão para `manual_review`.

### Bloco 3 — MCP server de consulta

- Mesmo padrão do `mcp-agrofit` existente, mas lendo do SQLite local.
- Tools: `buscar_dose(cultura, praga|produto)`, `detalhar_produto(numero_registro)`,
  `listar_culturas()`, `listar_pragas(cultura)`.
- Dose vem **sempre** de query determinística — o LLM cliente nunca gera número.
- Toda resposta inclui a referência da bula (produto, registro MAPA, arquivo/página).

## Modelo de dados (SQLite)

Compatível com FrutiT por chaves naturais: `numero_registro` (MAPA) e
`praga_nome_cientifico` (o `Organismo.slug_base` do FrutiT deriva do científico).

```sql
produtos(
  numero_registro TEXT PK,     -- chave natural MAPA
  marca_comercial, titular, formulacao,
  classificacao_toxicologica, classificacao_ambiental,
  url_agrofit, bula_arquivo, bula_url
)
ingredientes_ativos(produto_fk, nome, grupo_quimico, concentracao, unidade)
indicacoes(                     -- núcleo do dataset
  id PK, produto_fk,
  cultura, praga_nome_cientifico, praga_nome_comum,
  dose_min REAL, dose_max REAL, dose_unidade TEXT,      -- ex: mL/100L, L/ha, g/planta
  volume_calda_min, volume_calda_max, volume_calda_unidade,
  num_max_aplicacoes INT, intervalo_aplicacao_dias TEXT,
  carencia_dias INT, epoca_aplicacao TEXT,
  fonte_pagina INT, fonte_trecho TEXT,                   -- proveniência
  status TEXT  -- extraido | validado | manual_review
)
```

Unidades ficam **como declaradas na bula** (vocabulário controlado, sem conversão) —
converter mL/100L↔L/ha exige volume de calda e introduz erro.

## Tratamento de erros

- Coletor: falha de download não interrompe o lote; registra e segue. Retry manual.
- Extração: bula ilegível/escaneada → `manual_review`, nunca chute.
- MCP: consulta sem resultado responde "sem registro na base" — nunca aproxima.

## Testes / verificação

- Coletor: contagem final vs. `X-Records-Count`; amostragem de PDFs válidos (magic bytes).
- Extração: gabarito manual de ~30 bulas conferidas à mão; medir acurácia campo a
  campo antes de rodar o lote completo. Meta: ≥95% nos campos numéricos.
- MCP: testes das tools contra um SQLite fixture.

## Riscos conhecidos

- Layout de tabela varia por fabricante (medido em amostra de 12) — mitigado pelo
  gabarito + fila de revisão manual.
- ~6% dos produtos sem bula na API — ficam com `indicacoes` vazias, sinalizados.
- Credenciais Embrapa hoje commitadas em `.bob/mcp.json` — mover para `.env` (fora
  do git) ao publicar o repo.
