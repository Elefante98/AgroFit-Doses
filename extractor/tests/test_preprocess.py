from pathlib import Path

from preprocess import processar_bula, selecionar_paginas, tabela_de_uso

FIXTURE = Path(__file__).parent / "fixtures" / "bula_fixture.pdf"


def pag(numero, texto, tabela_uso=False):
    return {"numero": numero, "texto": texto, "tabela_uso": tabela_uso}


def test_seleciona_por_titulo_de_secao_sem_adjacencia():
    # titulo de secao seleciona a propria pagina; prosa com "dose"/"cultura"
    # soltas NAO seleciona mais (heuristica v3 — medida em 20 bulas reais)
    paginas = [pag(1, "capa do produto"), pag(2, "INSTRUÇÕES DE USO"),
               pag(3, "na agricultura, a dose certa importa"), pag(4, "y")]
    assert selecionar_paginas(paginas) == {2}


def test_tabela_de_uso_puxa_adjacentes():
    paginas = [pag(1, "x"), pag(2, "y", tabela_uso=True), pag(3, "z"), pag(4, "w")]
    # pagina 2 (tabela de uso) + adjacentes 1 e 3; pagina 4 fica fora
    assert selecionar_paginas(paginas) == {1, 2, 3}


def test_nada_casa_nada_sai():
    assert selecionar_paginas([pag(1, "só capa"), pag(2, "endereço")]) == set()


def test_tabela_de_uso_exige_estrutura_e_conteudo():
    # tabela real de dose: >=3 linhas, >=2 colunas, conteudo de dose/cultura
    assert tabela_de_uso([["CULTURA", "DOSE"], ["Uva", "30 mL/100L"], ["Soja", "0,5 L/ha"]])
    # sublinhado detectado como "tabela" de 1 celula (falso-positivo de capa)
    assert not tabela_de_uso([["______"]])
    # estrutura ok mas sem conteudo de uso
    assert not tabela_de_uso([["Lote", "X"], ["Fabricação", "Y"], ["Vencimento", "Z"]])


def test_processar_bula_real_gera_txt_com_paginas_e_dose(tmp_path):
    destino = processar_bula(FIXTURE, tmp_path)
    assert destino.suffix == ".txt"
    conteudo = destino.read_text(encoding="utf-8")
    assert "=== PÁGINA" in conteudo
    assert "DOSE" in conteudo.upper()
    assert "Uva" in conteudo  # a tabela de Uva do Domark precisa sobreviver ao recorte


def test_bula_curta_vira_scan(tmp_path):
    # PDF mínimo válido de 1 página em branco (sem texto)
    import pdfplumber  # noqa: F401  (garante dep presente)
    vazio = tmp_path / "vazio.pdf"
    vazio.write_bytes(_pdf_uma_pagina_em_branco())
    destino = processar_bula(vazio, tmp_path)
    assert destino.suffix == ".scan"
    assert destino.read_bytes() == b""


def _pdf_uma_pagina_em_branco() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF"
    )
