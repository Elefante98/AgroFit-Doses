# AgroFit Doses — Design

**Data:** 2026-08-17
**Status:** Aprovado (abordagem C) — revisão rodada 1 aplicada

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

## Stack

- Blocos 1 e 3: Node/TypeScript (mesmo stack do `mcp-agrofit` existente).
- Bloco 2 (pré-processamento e import): Python 3 + `pdfplumber`, com
  `requirements.txt` próprio em `extractor/`.
- Convenção de nomes das tools MCP: **português** (`buscar_dose`), divergindo
  deliberadamente do `mcp-agrofit` (inglês) — o público-alvo é agrônomo brasileiro.

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

### Bloco 1 — Coletor (script Node/TS, sem IA)

- Pagina `GET /produtos-formulados` (43 páginas × 100) e salva um JSON por produto
  em `raw/produtos/<numero_registro>.json`.
- Baixa o PDF de cada documento `tipo_documento == "Bula"` para
  `raw/bulas/<numero_registro>.pdf`. Se um produto tiver **mais de uma** bula,
  salva `<numero_registro>_2.pdf`, `_3.pdf`… e loga o caso em
  `raw/failures.jsonl` (tipo `multi_bula`) para decisão manual — nunca sobrescreve.
- Requisitos: retomável (pula o que já existe), rate-limit educado (~1 req/s),
  `--http1.1` + User-Agent de navegador (o servidor do MAPA rejeita curl puro),
  log de falhas em `raw/failures.jsonl` para retry.
- Token OAuth2 renovado automaticamente (expira ~25 min; padrão de cache igual ao
  de `mcp-agrofit/src/index.ts`).

### Bloco 2 — Extração (Claude Code, subscription, sem custo de API)

Três sub-etapas com artefatos intermediários em disco — o estado nunca vive só
numa sessão de chat:

**2a. Pré-processamento (script Python).** Para cada bula, extrai com `pdfplumber`
as páginas candidatas e grava `pre/<numero_registro>.txt`. Heurística de seleção:
página entra se (i) contém tabela detectada pelo pdfplumber **ou** (ii) casa
keyword (`DOSE`, `INSTRUÇÕES DE USO`, `CULTURA`, `MODO DE APLICA`, `INTERVALO`,
`CARÊNCIA`, case/acento-insensitive). **Na dúvida, inclui** — errar para mais
texto, nunca para menos. Bula cujo texto extraído < 500 chars (provável scan) →
estado `manual_review` direto.

**2b. Extração (Claude, em lotes por sessão).** Claude lê `pre/<reg>.txt` e emite
`extracted/<numero_registro>.json` com os registros no schema abaixo. Um arquivo
por bula, **mesmo quando vazio** (`{"registros": []}` + motivo) — arquivo presente
= bula processada; é isso que dá retomabilidade entre sessões.

**2c. Import + validação (script Python, determinístico).** Lê `extracted/*.json`,
valida e grava no SQLite. Mantém manifesto `estado.json` por bula:
`pendente | pre_ok | extraida | importada | vazia | manual_review`.

Validações no import:
- **Precisão:** dose numérica > 0; unidade pertence ao vocabulário (abaixo);
  (cultura, praga) deve casar com o `indicacao_uso` da API do produto.
- **Recall (validação inversa):** todo par (cultura, praga) do `indicacao_uso`
  da API **sem** registro extraído correspondente marca o produto como
  `incompleto` e entra na fila. Cobertura agregada (% de pares da API com dose
  extraída) é métrica de aceite do lote.
- **Matching cultura/praga:** normalização = lowercase + sem acento + sem autor
  botânico (parênteses no fim do científico). Casa por nome comum OU científico.
  Bula só com nome comum → `praga_nome_cientifico` preenchido a partir da API
  quando o match normalizado é único; ambíguo → `manual_review`.

**Vocabulário de unidades** (seed da amostra medida; extensível):
`L/ha`, `mL/ha`, `kg/ha`, `g/ha`, `mL/100L`, `g/100L`, `L/100L`,
`g/planta`, `mL/planta`, `L/planta`, `mL/100kg sementes`, `g/100kg sementes`,
`g/m²`, `mL/m²`. Unidade fora da lista → `manual_review`; se legítima, entra no
vocabulário (arquivo `unidades.json` versionado) e os registros pendentes são
revalidados no próximo import — o ciclo é: fila → decisão → vocabulário → re-run.

Proveniência: cada registro carrega arquivo da bula, página e trecho de origem.

### Bloco 3 — MCP server de consulta

- Mesmo transporte/estrutura do `mcp-agrofit`, lendo do SQLite local.
- Tools:
  - `buscar_dose(cultura: obrigatória, praga?: string, produto?: string)` —
    `praga` e `produto` opcionais e independentes (pode passar ambos); `praga`
    casa por nome comum ou científico (normalizado); sem nenhum dos dois, retorna
    erro pedindo ao menos um filtro.
  - `detalhar_produto(numero_registro)`
  - `listar_culturas()`, `listar_pragas(cultura)`
- Dose vem **sempre** de query determinística — o LLM cliente nunca gera número.
- Respostas distinguem três casos: resultado encontrado; **produto existe mas sem
  bula disponível** (`bula_arquivo IS NULL`); sem registro na base. Nunca aproxima.
- Toda resposta inclui a referência da bula (produto, registro MAPA, arquivo/página).

## Modelo de dados (SQLite)

```sql
produtos(
  numero_registro TEXT PK,     -- chave natural MAPA
  marca_comercial, titular, formulacao,
  classificacao_toxicologica, classificacao_ambiental,
  url_agrofit, bula_arquivo, bula_url,   -- bula_arquivo NULL = sem bula
  estado TEXT                  -- manifesto: pendente|pre_ok|extraida|importada|vazia|manual_review|incompleto
)
ingredientes_ativos(id PK, produto_fk, nome, grupo_quimico, concentracao, unidade)
indicacoes(                     -- núcleo do dataset
  id PK, produto_fk,
  cultura, praga_nome_cientifico, praga_nome_comum,
  dose_min REAL, dose_max REAL, dose_unidade TEXT,  -- dose única → min = max
  volume_calda_min, volume_calda_max, volume_calda_unidade,
  num_max_aplicacoes INT,
  intervalo_aplicacao TEXT,     -- texto da bula (ex: "7 a 15 dias")
  carencia_dias INT,            -- NULL quando não numérico…
  carencia_texto TEXT,          -- …e o texto original vem aqui (ex: "UNA")
  epoca_aplicacao TEXT,
  fonte_pagina INT, fonte_trecho TEXT,               -- proveniência
  status TEXT  -- extraido | validado | manual_review
)
```

**Sobre o FrutiT (correção verificada em código):** o `Produto` do FrutiT
([produto.py](D:/Frutit/apps/api/app/models/produto.py)) **não** tem campo de
registro MAPA, e o `Organismo.slug_base` deriva de nome **comum** slugificado
(prefixo de `organismo_config.slug`, ver `seed.py::seed_organismos_base`), não do
científico. Integração futura exigirá: adicionar `numero_registro` ao Produto do
FrutiT e mapear organismos por **nome comum normalizado**. Este schema já guarda
os dois nomes (comum e científico) justamente para permitir esse join.

Unidades ficam **como declaradas na bula** (vocabulário controlado, sem conversão) —
converter mL/100L↔L/ha exige volume de calda e introduz erro.

## Tratamento de erros

- Coletor: falha de download não interrompe o lote; registra e segue. Retry manual.
- Extração: bula ilegível/escaneada → `manual_review`, nunca chute.
- MCP: consulta sem resultado responde "sem registro na base" — nunca aproxima.

## Testes / verificação

- Coletor: contagem final vs. `X-Records-Count`; amostragem de PDFs válidos
  (magic bytes `%PDF`).
- Extração — **piloto antes do lote completo**: gabarito manual de ~30 bulas,
  **estratificado por titular (máx. 2 por fabricante)** para cobrir variação de
  layout. Metas de aceite do piloto:
  - acurácia ≥95% nos campos numéricos (dose, calda, carência, nº aplicações);
  - taxa de `manual_review` ≤15% — acima disso, ajustar heurística/prompt e
    re-medir **no mesmo gabarito** antes de liberar o lote (loop declarado).
- MCP: testes das tools contra um SQLite fixture, incluindo os três casos de
  resposta (encontrado / produto sem bula / sem registro).

## Riscos conhecidos

- Layout de tabela varia por fabricante (medido em amostra de 12) — mitigado pelo
  piloto estratificado + validação inversa de recall + fila de revisão manual.
- ~6% dos produtos sem bula na API — ficam com `bula_arquivo NULL` e `indicacoes`
  vazias; o MCP responde o caso explicitamente.
- Credenciais Embrapa vivem em `.bob/mcp.json`, **fora do git** (`.bob/` está no
  `.gitignore` desde o primeiro commit); o coletor lê de `.env` (também ignorado).
