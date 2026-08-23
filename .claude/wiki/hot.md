# hot.md — estado atual (AgroFit Doses)

> Atualizado: 2026-08-23 (sessão agendada de extração em massa)

## Extração em massa — progresso

- Preprocess **v3 re-rodado em todas as bulas** (`pre/*.txt` da v1 apagados):
  3.960 recortes + 39 marcadores `.scan`, 0 erros.
- **190 bulas extraídas e importadas** (30 do piloto + 160 da massa).
  Banco: **25.283 registros** — 21.120 `validado`, 3.704 `validado_bula`,
  459 `manual_review` (**1,8%**, meta ≤15% ✅).
- **Restam ~3.770 bulas** (`pre/*.txt` sem `extracted/*.json`).
- Ondas fechadas: lote 1 (40), onda 1 (30, regs 107-309), onda 2 (30, regs 310-521),
  onda 3 (60, do topo da numeração para baixo). Onda 4 (60) em voo ao encerrar.

### Como retomar
O pipeline deriva estado do disco: pegue os `pre/*.txt` sem `extracted/*.json`,
lotes de ~5 por subagente, prompt em `extractor/EXTRACAO_MASSA.md` + `EXTRACAO.md`.
**A onda 3 desceu a partir do maior nº de registro; a onda 2 subiu até 521.**
Manter direções separadas evita colisão se duas sessões rodarem juntas
(aconteceu nesta sessão: uma sessão sucessora commitou os arquivos órfãos da outra).

## Contrato endurecido — `extractor/EXTRACAO_MASSA.md`

Regras (a)-(j) da certificação + duas descobertas desta sessão:
- **(k) `cultura` nunca é null** → `"Não Atrelado a Cultura"` (valor canônico do
  AgroFit). Null quebra o `import_db.py` (NOT NULL) e derruba o lote inteiro.
- **(l) grafia canônica da unidade, sem "p.c."** (`g p.c./ha` → `g/ha`). Recuperou
  191 registros que estavam em `manual_review` à toa nas bulas 122/123/211/217/220.

## Débito aberto (precisa de decisão do Moisés)

1. **Cobertura em 80,9%** dos pares da API nas 190 bulas (meta do piloto: ≥90%).
   52 das 190 têm cobertura de 100%. Maior buraco isolado: **reg. 3078394**
   (Glifosato Nortox) — 1.675 pares sem dose, ~41% do buraco total.
   Causa: a seção de dose 1.2.1 lista **só plantas daninhas**, sem coluna de
   cultura; o título dela ("em áreas de plantio direto…") não nomeia cultura, e a
   seção 1.1 lista culturas de **várias modalidades diferentes** (perenes em capina
   química, plantio direto, pastagem, eucalipto). Expandir para as 17 culturas da
   API criaria pares falsos. Ficou como `"Não Atrelado a Cultura"` →
   `validado_bula` (dose correta, servida com proveniência). **Decidir:** herbicida
   de capina química merece regra própria de expansão?
2. **Vocabulário de unidades** — a massa trouxe unidades reais de bula fora do
   `unidades.json`, todas transcritas literais e retidas em `manual_review`
   (comportamento correto, fail-closed): `adultos/ha` (biológico), `mL/L`, `mL/tonelada`,
   `g/tonelada`, `pastilha/tonelada`, `pastilha/15 sacos de 60 kg`, `L/1000 covas`,
   `L/100kg sementes`, `mL/kg de sementes`. Estender o vocabulário é decisão de spec.
3. **Faixas por estádio**: piloto tem registro-por-coluna (8514) E faixa global
   (30723). A massa segue registro-por-faixa; decidir se re-normaliza o 30723.
4. **50 manual_review do piloto** = produtos sem alvo biológico (reguladores/câmara)
   — modelagem "alvo = processo" pendente.
5. **Repo renomeado no GitHub** para `Elefante98/AgroFit-Doses` (o push por
   `FrutiT` ainda funciona por redirect). Trocar a URL do remote local pede
   permissão que o classificador do auto mode nega.

## Onde estamos

- Piloto de 30 bulas CERTIFICADO (4 rodadas de auditores independentes, 3 modelos,
  rodada final sem erros de conteúdo).
- Repos publicados: github.com/Elefante98/AgroFit-Doses (código+dados, ex-FrutiT) e
  github.com/Elefante98/bulas (material de validação).
- Memória longa em `~/.claude/projects/D--Pragas-Uva/memory/`.
