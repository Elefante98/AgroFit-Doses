# AgroFit Doses

Banco local estruturado de doses de defensivos agrícolas por (produto, cultura,
praga), extraído das bulas em PDF registradas no [AgroFit/MAPA](https://agrofit.agricultura.gov.br/),
exposto via [MCP](https://modelcontextprotocol.io/) para consulta por agrônomos.

## O que é / o que não é

**É:** uma ferramenta de *consulta à bula registrada* — "o que o MAPA autoriza
para este produto, nesta cultura, contra esta praga, e em qual dose". Toda
resposta referencia a bula de origem (arquivo/URL/página).

**Não é:** um sistema de recomendação ou prescrição de defensivos. Indicar
qual produto e dose aplicar em uma lavoura é ato privativo de engenheiro
agrônomo, sujeito a receituário agronômico (**Lei 7.802/89**). Este projeto
apenas facilita a consulta ao que já está registrado — a decisão de uso
continua sendo do profissional habilitado.

## Arquitetura — 3 blocos

```
[API AgroFit] ──► Bloco 1: Coletor ──► raw/ (JSON + PDFs)
                                          │
                  Bloco 2a: pré-proc ◄────┘   (script: pdfplumber → trechos)
                  Bloco 2b: extração          (Claude → extracted/<reg>.json)
                  Bloco 2c: import + validação (script → SQLite doses.db)
                       │
                  Bloco 3: MCP server ──► cliente (Claude / Ollama futuro)
```

- **Bloco 1 — Coletor** (`coletor/`, Node/TS): baixa produtos e bulas em PDF da
  API AgroFit para `raw/`.
- **Bloco 2 — Extração** (`extractor/`, Python + Claude): pré-processa os PDFs,
  extrai os dados de dose (assistido por Claude) e importa/valida no SQLite.
- **Bloco 3 — MCP server** (`mcp-doses/`, Node/TS): expõe o banco local via MCP
  para consulta por um cliente LLM.

Detalhes completos do design (modelo de dados, regras de validação, estados do
pipeline) em [`docs/superpowers/specs/2026-08-17-agrofit-doses-design.md`](docs/superpowers/specs/2026-08-17-agrofit-doses-design.md).

## Como rodar cada bloco

### Bloco 1 — Coletor

```bash
cd coletor
npm install
npm run collect
```

Requer `CONSUMER_KEY`/`CONSUMER_SECRET` da API Embrapa (mesmas credenciais do
`mcp-agrofit`) em `.env`. Retomável — pula o que já existe em `raw/`.

### Bloco 2a — Pré-processamento

```bash
cd extractor
pip install -r requirements.txt
python preprocess.py
```

Lê `raw/bulas/*.pdf` e grava `pre/<numero_registro>.txt` (ou `.scan`, quando o
PDF é escaneado e precisa de revisão manual).

### Bloco 2b — Extração

Procedimento manual assistido por Claude Code, descrito em
[`extractor/EXTRACAO.md`](extractor/EXTRACAO.md). Gera `extracted/<numero_registro>.json`.

### Bloco 2c — Import + validação

```bash
cd extractor
python import_db.py
```

Carrega `raw/produtos/*.json` (metadata, sempre) e `extracted/*.json`
(indicações validadas) em `data/doses.db`, e recalcula `estado.json` e o
relatório de cobertura.

### Bloco 3 — MCP server

```bash
cd mcp-doses
npm install
npm start
```

Lê `data/doses.db` (caminho configurável via `DOSES_DB`) e expõe as tools
`buscar_dose`, `detalhar_produto`, `listar_culturas`, `listar_pragas` via
stdio. Registro de exemplo em `.bob/mcp.json` (fora do git):

```json
"doses": { "command": "npx", "args": ["tsx", "D:\\Pragas Uva\\mcp-doses\\src\\index.ts"] }
```

## Estado do dataset

Escopo pretendido: todas as culturas do AgroFit (4.252 produtos formulados,
~94% com bula em PDF). **A extração em massa (blocos 2a-2c) ainda está em
construção** — o banco atual reflete apenas a amostra usada nos testes e
smoke tests de cada bloco, não o dataset completo.

## Aviso legal

Consulta à bula registrada no MAPA — não é recomendação. Receituário
agronômico é ato privativo de engenheiro agrônomo (**Lei 7.802/89**).

## Créditos / fontes

- Dados de produtos, bulas e culturas: [AgroFit](https://agrofit.agricultura.gov.br/),
  Ministério da Agricultura e Pecuária (MAPA).
- Acesso programático via [API AgroFit da Embrapa](https://www.embrapa.br/) (API Store Embrapa).
