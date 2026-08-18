# Procedimento de extração (Bloco 2b)

Executor: Claude (Code), em lotes por sessão. Custo: subscription — nunca API paga.

## Regras inegociáveis
1. Transcreva, não interprete: todo número vem literalmente do `pre/<reg>.txt`.
   Dose ilegível, em prosa ambígua ou fora de tabela → NÃO chute: emita o
   registro com `dose_min`/`dose_max` como vieram (ou null) e deixe a validação
   reprovar para `manual_review`.
2. Um arquivo de saída por bula, SEMPRE — mesmo sem nenhum registro:
   `{"numero_registro": "<reg>", "registros": [], "motivo": "<por quê>"}`.
   Arquivo presente = bula processada (é a retomabilidade do pipeline).
3. Unidades exatamente como na bula, sem converter (mL/100L NUNCA vira L/ha).
   Grafia canônica do vocabulário `unidades.json` (ex.: `mL/100L`, `L/ha`).
4. Valor único → min = max. Faixa "30-50" → min=30, max=50.
5. `fonte_pagina` = número do marcador `=== PÁGINA N ===` de onde o dado saiu;
   `fonte_trecho` = linha da tabela/texto de origem (recortada, até ~120 chars).
6. Volume de calda: número em `volume_calda_min/max` SÓ quando a bula dá um
   volume único; quando varia por modalidade (terrestre/aérea/costal...), os
   numéricos ficam null e o texto literal vai em `volume_calda_outros`
   (ex: "Terrestre: 100-300 L/ha; Aérea: 30-50 L/ha").
7. Carência: número em `carencia_dias`; texto ("UNA", "Não determinado…") em
   `carencia_texto` com `carencia_dias: null`.

## Formato de saída (contrato com import_db.py)
```json
{
  "numero_registro": "6099",
  "registros": [
    {
      "cultura": "Uva", "praga_nome_comum": "Oídio", "praga_nome_cientifico": "Uncinula necator",
      "dose_min": 30, "dose_max": 30, "dose_unidade": "mL/100L",
      "volume_calda_min": 1000, "volume_calda_max": 1200, "volume_calda_unidade": "L/ha",
      "volume_calda_outros": null,
      "num_max_aplicacoes": null, "intervalo_aplicacao": "7 a 15 dias",
      "carencia_dias": 7, "carencia_texto": null,
      "epoca_aplicacao": "preventivo", "fonte_pagina": 4,
      "fonte_trecho": "UVA | Oídio | Uncinula necator | - | 30 | 1000 - 1200"
    }
  ]
}
```
Campos desconhecidos = null. Um registro por (cultura, praga) — praga com nomes
comuns múltiplos na mesma linha da bula = um registro por nome comum só se as
doses diferirem; senão um registro com o primeiro nome.
Cultura agrupada na bula ("Citros", "todas as culturas com ocorrência do alvo")
→ um registro por cultura SÓ se a bula listar as culturas; senão um registro com
a cultura como está escrita (a validação manda para manual_review — correto).

## Procedimento por sessão (lote de ~40 bulas)
1. Escolher regs: arquivos em `pre/*.txt` sem correspondente em `extracted/`.
2. Para cada reg: ler `pre/<reg>.txt`, montar o JSON, gravar `extracted/<reg>.json`.
3. Ao final do lote: `cd extractor && python import_db.py` e conferir o
   relatório de cobertura + contagem de manual_review.
4. Commitar o lote: `git add extracted && git commit -m "data: lote extração <faixa>"`.

## Piloto (OBRIGATÓRIO antes do lote completo — spec, seção Testes)
1. Selecionar ~30 bulas estratificadas por titular (máx. 2 por fabricante):
   `python - <<'EOF'` com groupby de titular sobre `raw/produtos/*.json`.
2. Extrair as 30 conforme acima; para cada uma, conferir MANUALMENTE contra o
   PDF (humano abre o PDF, compara campo a campo) e registrar acertos/erros
   numa planilha `piloto.csv` (reg, campo, extraido, correto, ok?).
3. Metas: ≥95% de acurácia nos campos numéricos E ≤15% de taxa de manual_review
   E cobertura ≥90% medida SÓ nos 30 regs do piloto:
   `python -c "from pathlib import Path; from import_db import conectar, relatorio_cobertura; regs=set(Path('piloto.txt').read_text().split()); print(relatorio_cobertura(conectar(Path('../data/doses.db')), regs))"`
   Abaixo → ajustar este documento (prompt) ou a heurística do preprocess →
   re-extrair as MESMAS 30 → re-medir.
4. Só liberar o lote completo com as três metas batidas.
