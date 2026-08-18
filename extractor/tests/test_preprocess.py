from pathlib import Path

from preprocess import processar_bula, selecionar_paginas

FIXTURE = Path(__file__).parent / "fixtures" / "bula_fixture.pdf"


def pag(numero, texto, tem_tabela=False):
    return {"numero": numero, "texto": texto, "tem_tabela": tem_tabela}


def test_seleciona_por_keyword_normalizada():
    paginas = [pag(1, "capa do produto"), pag(2, "MODO DE APLICAÇÃO e doses"), pag(3, "x"), pag(4, "y")]
    # 2 casa keyword; 1 e 3 entram por adjacência (spec, item iii); 4 fica fora
    assert selecionar_paginas(paginas) == {1, 2, 3}


def test_seleciona_por_tabela_e_adjacentes():
    paginas = [pag(1, "x"), pag(2, "y", tem_tabela=True), pag(3, "z"), pag(4, "w")]
    # página 2 (tabela) + adjacentes 1 e 3; página 4 fica fora
    assert selecionar_paginas(paginas) == {1, 2, 3}


def test_nada_casa_nada_sai():
    assert selecionar_paginas([pag(1, "só capa"), pag(2, "endereço")]) == set()


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
