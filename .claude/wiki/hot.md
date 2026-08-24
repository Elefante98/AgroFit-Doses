# hot.md — estado atual (AgroFit Doses)

> Atualizado: 2026-08-24 (sessão agendada de extração em massa — ondas 8-13)

## Extração em massa — progresso

- Preprocess **v3 re-rodado em todas as bulas** (`pre/*.txt` da v1 apagados):
  3.960 recortes + 39 marcadores `.scan`, 0 erros.
- **809 bulas extraídas e importadas** (30 do piloto + 779 da massa).
  Banco: **70.942 registros** — 58.421 `validado`, 11.253 `validado_bula`,
  1.268 `manual_review` (**1,8%**, meta ≤15% ✅).
- **Restam 3.151 bulas** (`pre/*.txt` sem `extracted/*.json`).
- Ondas fechadas: lote 1 (40), ondas 1-2 (60), ondas 3-4 (120, descendo do maior
  nº de registro), ondas 5-6 (120), onda 7 parcial (36), ondas 8-10 (180) e
  **ondas 11-13 (180, regs 2807-4024)**, todas subindo do menor nº do backlog.
- **Onda 14 ficou parcial**: 5 de 60 bulas (4098, 4111, 4323, 4494, 4496) — a sessão
  bateu no limite de uso e os 12 subagentes morreram por erro de API. As 55 bulas não
  gravadas voltaram ao backlog sozinhas; nada a consertar. Essas 5 estão commitadas
  mas **ainda não importadas** — rodar `python extractor/import_db.py` na retomada.
- **LOOP AGENDADO DESATIVADO em 2026-08-24 a pedido do Moisés**
  (`agrofit-extracao-massa-loop`, cron `0 */6 * * *`). Não reativar sem pedido
  explícito dele.

### Como retomar
O pipeline deriva estado do disco: pegue os `pre/*.txt` sem `extracted/*.json`,
lotes de ~5 por subagente, ~12 subagentes em paralelo. O prompt do subagente manda
ler `extractor/EXTRACAO.md` + `extractor/EXTRACAO_MASSA.md` (regras a-l) e **não**
rodar `import_db.py` (o coordenador roda uma vez no fim da onda — subagentes rodando
em paralelo batem em `database is locked`).
**As ondas 3 e 4 desceram a partir do maior nº de registro (já foram até 419003);
as demais subiram, chegando ao reg. 4024 (onda 13).** Manter direções separadas evita
colisão se duas sessões rodarem juntas.

## Contrato endurecido — `extractor/EXTRACAO_MASSA.md`

Regras (a)-(j) da certificação + duas descobertas desta sessão:
- **(k) `cultura` nunca é null** → `"Não Atrelado a Cultura"` (valor canônico do
  AgroFit). Null quebra o `import_db.py` (NOT NULL) e derruba o lote inteiro.
- **(l) grafia canônica da unidade, sem "p.c."** (`g p.c./ha` → `g/ha`). Recuperou
  191 registros que estavam em `manual_review` à toa nas bulas 122/123/211/217/220.

## Débito aberto (precisa de decisão do Moisés)

1. **Cobertura em 81,4%** dos pares da API nas 250 bulas (meta do piloto: ≥90%).
   Maior buraco isolado: **reg. 3078394** (Glifosato Nortox) — 1.675 pares sem dose.
   Causa: a seção de dose 1.2.1 lista **só plantas daninhas**, sem coluna de cultura;
   o título dela ("em áreas de plantio direto…") não nomeia cultura, e a seção 1.1
   lista culturas de **várias modalidades diferentes** (perenes em capina química,
   plantio direto, pastagem, eucalipto). Expandir para as 17 culturas da API criaria
   pares falsos. Ficou `"Não Atrelado a Cultura"` → `validado_bula` (dose correta,
   servida com proveniência). **Decidir:** herbicida de capina química merece regra
   própria de expansão? Comparar com o reg. 898793 (Roundup), onde a seção de dose
   TEM cabeçalho "CULTURAS: …" e a expansão foi feita (2.820 registros).
2. **Identidade — 2 casos que a regra (a) não previu:**
   - `1358490`: bula imprime `01358410` (1 dígito de diferença), marca confere
     (HERBI-D 480, Adama) e `1358410` não existe no dataset. Extraído como **JSON
     vazio** conforme a regra. Provável erro de digitação da bula → conferir.
   - `1238703`: bula imprime `0123870003`. **Foi extraído** (7 registros) porque
     marca (Larvin 350), titular (Bayer), i.a. (tiodicarbe 350 g/L) e **os 6 pares
     cultura×praga da API batem exatamente**. É a única exceção aberta à regra (a);
     ratificar ou reverter para JSON vazio.
3. **Vocabulário de unidades** — a massa trouxe muitas unidades reais de bula fora do
   `unidades.json`, todas transcritas literais e retidas em `manual_review`
   (fail-closed correto): `adultos/ha`, `mL/L`, `mL/ton`, `g/tonelada`,
   `pastilha/tonelada`, `pastilha/15 sacos de 60 kg`, `L/1000 covas`, `g/orifício`,
   `g/pé`, `mL/1000 plantas`, `mL/100m2`, `mL/1000m3`, `kg/100kg sementes`,
   `L/100kg sementes`, `mL/kg de sementes`, `kg/100kg bulbilhos`. Estender o
   vocabulário é decisão de spec (passa pelo gate de review).
4. **Faixas por estádio**: piloto tem registro-por-coluna (8514) E faixa global
   (30723). A massa segue registro-por-faixa; decidir se re-normaliza o 30723.
5. **50 manual_review do piloto** = produtos sem alvo biológico (reguladores/câmara)
   — modelagem "alvo = processo" pendente.
6. **Repo renomeado no GitHub** para `Elefante98/AgroFit-Doses` (push por `FrutiT`
   ainda funciona por redirect). Trocar a URL do remote local pede permissão que o
   classificador do auto mode nega — fazer à mão:
   `git remote set-url origin https://github.com/Elefante98/AgroFit-Doses.git`

## Onde estamos

- Piloto de 30 bulas CERTIFICADO (4 rodadas de auditores independentes, 3 modelos,
  rodada final sem erros de conteúdo).
- Repos publicados: github.com/Elefante98/AgroFit-Doses (código+dados, ex-FrutiT) e
  github.com/Elefante98/bulas (material de validação).
- Memória longa em `~/.claude/projects/D--Pragas-Uva/memory/`.
