# Contrato endurecido da extração em massa (fase 2b — pós-certificação)

Vale **junto com** `EXTRACAO.md` (regras inegociáveis, formato de saída, unidades).
Este arquivo acrescenta o que a certificação do piloto (4 rodadas de auditores
independentes, 2026-08-22) provou ser necessário. Em conflito, este vence.

## Ferramentas
- **Os PDFs não abrem com a ferramenta Read nesta máquina** (poppler ausente).
  Use Python via Bash: `import fitz` (PyMuPDF) e/ou `pdfplumber`.
- `pre/<reg>.txt` é um **recorte** das páginas candidatas, com marcadores
  `=== PÁGINA N ===`. Use-o para achar as tabelas rápido, mas **confirme no PDF**:
  o texto corrido embaralha colunas em muitas bulas. Quando a tabela for complexa,
  extraia por células/coordenadas (`page.get_text("dict")`, `page.find_tables()`,
  `pdfplumber.Page.extract_table`).

## Regras endurecidas (a–j)

**(a) Checagem de identidade.** O nº de registro do MAPA impresso na bula tem de
bater com o nome do arquivo (zeros à esquerda ok). A **marca comercial pode
divergir** do título da bula (ex.: reg. 315 é "Grant" na API e "2,4-D 806 SL AGCN"
na bula) — identidade é **pelo número**, nunca pela marca. Divergência de número =
**não extrair**: grave o JSON vazio com
`{"numero_registro": "<reg>", "registros": [], "motivo": "identidade divergente: bula traz registro NNN"}`.

**(b) `fonte_pagina` = página física onde a LINHA está impressa.** Tabelas
transbordam página: verifique por espécie/linha, não pelo cabeçalho da tabela.

**(c) Expansão de culturas segue o cabeçalho da SEÇÃO de dose** — não a tabela de
volumes de calda nem outra seção vizinha.

**(d) Volumes que aparecem na seção "modo de aplicação"** (e não na tabela de uso)
vão em `volume_calda_outros` como texto literal, com os numéricos `null`.

**(e) Um registro por faixa rotulada.** Tabela com colunas/faixas rotuladas por
estádio, densidade de plantio ou tipo de solo → **um registro por rótulo**
(o rótulo entra em `epoca_aplicacao` ou no `fonte_trecho`, conforme o que a bula
rotula). Sem rótulo explícito → faixa global min–max.

**(f) Nomes compostos transcritos por inteiro** ("Antracnose Podridão-amarga";
"Cigarrinha das pastagens; Cigarrinha dos capinzais").

**(g) Dose em duas formas alternativas** ("X kg/ha ou Y g/100L") → **um registro
por forma**, mesmos demais campos.

**(h) `num_max_aplicacoes` fica `null`** quando a bula relativiza o número
("aplicar novamente se necessário", "repetir após cada corte").

**(i) A coluna de ingrediente ativo (g i.a./ha, kg i.a./ha) é descartada.**
Nunca a confunda com dose de produto comercial nem com volume de calda.

**(j) Célula de cultura genérica com rodapé nomeando culturas** ("demais culturas¹"
+ nota "¹ abacate, manga, ...") → **expanda para as culturas do rodapé**.

## Convenções herdadas do piloto
- Regulador de crescimento / tratamento de câmara sem alvo biológico: a espécie da
  **cultura** vai em `praga_nome_cientifico` (convenção do reg. 5102).
- Cultura agrupada que a bula **não** lista ("todas as culturas com ocorrência do
  alvo") → um registro com a cultura como está escrita (validação manda para
  `manual_review` — é o comportamento correto).
- Unidades só do vocabulário de `unidades.json`, sem converter.
- Um arquivo de saída por bula **sempre**, mesmo vazio (é a retomabilidade).
