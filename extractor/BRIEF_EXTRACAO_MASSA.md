# Brief da extração em massa (subagente extrator)

Você extrai doses de bulas do AgroFit Doses em `D:\Pragas Uva`. Antes de tudo leia
também `extractor/EXTRACAO.md` (contrato 2b) e um exemplo pronto `extracted/112.json`
(formato exato do JSON: objeto com `numero_registro` e lista `registros`; campos por
registro: cultura, praga_nome_comum, praga_nome_cientifico, dose_min, dose_max,
dose_unidade, volume_calda_min/max/unidade, volume_calda_outros, num_max_aplicacoes,
intervalo_aplicacao, epoca_aplicacao, carencia, fonte_pagina, fonte_trecho).

## Fontes por bula
- `pre/<num>.txt` — texto pré-processado (páginas relevantes já selecionadas): fonte principal.
- `raw/bulas/<num>.pdf` — PDF original. A ferramenta Read NÃO abre PDF aqui (poppler ausente);
  leia via Python/Bash com PyMuPDF (`import fitz`) e/ou pdfplumber (extract_tables resolve
  células mescladas; o texto corrido embaralha colunas — use células/coordenadas em tabelas
  complexas). Sempre confira doses no PDF quando o pre/ estiver ambíguo.

## Regras endurecidas (contrato da certificação — todas obrigatórias)
- (a) IDENTIDADE: nº MAPA impresso na bula deve bater com o nome do arquivo (zeros à esquerda
  ok). Se divergir, NÃO extraia: escreva `{"numero_registro":"<num>","registros":[],"erro":"identidade: bula imprime <X>"}`.
- (b) transcrição literal, sem conversão de unidades; dose única → dose_min = dose_max.
- (c) dose p.c. E i.a. na bula → registra o p.c.; coluna de i.a. descartada (nunca confundir i.a. com volume).
- (d) célula mesclada: dose herdada vale para todas as espécies/linhas abrangidas (marque "[dose herdada: ...]" no fonte_trecho).
- (e) grupo de culturas nomeado no cabeçalho da SEÇÃO de dose → um registro por cultura;
  célula de cultura genérica ("em todas as culturas...") com rodapé nomeando culturas → expanda para as do rodapé.
- (f) fonte_pagina = página FÍSICA do PDF (1-based) onde a LINHA da praga está impressa
  (tabelas transbordam páginas — verifique por espécie, não pelo cabeçalho).
- (g) tabela com colunas/faixas ROTULADAS de dose (estádio da daninha, densidade, tipo de solo)
  → um registro por faixa rotulada; a coluna deve casar com o rótulo. "3 - 4 aplicações" → use o teto.
- (h) volume de calda em TEXTO (rodapé/célula, variação por modalidade, ou seção de modo de
  aplicação) → `volume_calda_outros`; restrição de modalidade por cultura torna correta a
  ausência do volume aéreo nas demais.
- (i) nome comum composto transcrito por inteiro; dose em duas formas alternativas
  ("X kg/ha ou Y g/100L") → um registro por forma.
- (j) num_max_aplicacoes vazio quando a bula relativiza ("aplicar novamente se...", "repetir
  após cada corte"); produtos sem alvo biológico (dessecantes, maturadores, câmara) têm praga
  vazia — para reguladores de câmara, a espécie da cultura vai em praga_nome_cientifico.

## Saída
Um arquivo `extracted/<num>.json` por bula, SEMPRE (mesmo vazio), via
`json.dump(..., ensure_ascii=False, indent=1)`. NÃO rode import_db nem git.
NÃO delegue para outros subagentes — faça a extração você mesmo.
Texto final: só "<num>: <N> registros" (ou "ERRO identidade") por bula.
