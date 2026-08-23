# hot.md — estado atual (AgroFit Doses)

> Atualizado: 2026-08-23 01:30

## Extração em massa — progresso

- Preprocess v3 re-rodado: 3.999 bulas em `pre/`.
- **Lote 1 fechado: 40 bulas extraídas** (sessão agendada de 00:37, encerrou por
  limite às ~00:55; import+commit fechados depois). Banco: **70 produtos,
  9.172 registros** (7.519 validado, 1.572 validado_bula, 81 manual_review = 0,9%).
- Restam ~3.890 bulas. Contrato endurecido em `extractor/EXTRACAO.md` (regras a-j).

## Onde estamos

- **Piloto de 30 bulas CERTIFICADO** (4 rodadas de auditores independentes, 3 modelos,
  rodada final sem erros de conteúdo). Banco: **6.874 registros** — 5.540 `validado`,
  1.284 `validado_bula`, 50 `manual_review` (0,7%).
- Repos publicados: github.com/Elefante98/FrutiT (código+dados) e
  github.com/Elefante98/bulas (material de validação).
- Memória longa da sessão em `~/.claude/projects/D--Pragas-Uva/memory/` (convenções
  consolidadas da certificação estão lá e devem migrar para ADRs desta wiki).

## Próximo passo (LIBERADO, agendado)

**Extração em massa das ~3.930 bulas restantes**:
1. Apagar `pre/*.txt` antigos (heurística v1) e re-rodar `extractor/preprocess.py` (v3).
2. Extrair em lotes conforme `extractor/EXTRACAO.md` + convenções da certificação
   (checagem de identidade nº MAPA impresso × nome do arquivo; página física da linha;
   expansão pelo cabeçalho da seção de dose; volume de seção em `volume_calda_outros`;
   um registro por faixa rotulada de estádio/densidade/solo quando houver rótulos).
3. `import_db.py` + relatório de cobertura por lote; commit de `extracted/` por lote.

## Débito aberto

- Representação de faixas por estádio: piloto tem registro-por-coluna (8514) E faixa
  global (30723). Massa segue registro-por-faixa; decidir se re-normaliza o 30723.
- 50 manual_review = produtos sem alvo biológico (reguladores/câmara) — modelagem
  "alvo = processo" pendente de decisão do Moisés.
- Renomear repo FrutiT no GitHub (decisão do Moisés).
