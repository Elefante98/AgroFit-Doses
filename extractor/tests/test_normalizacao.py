from normalizacao import normalizar, sem_autor


def test_normalizar_caixa_acento_espacos():
    assert normalizar("  Oídio ") == "oidio"
    assert normalizar("CANA-DE-AÇÚCAR") == "cana-de-acucar"
    assert normalizar("Uva  de   mesa") == "uva de mesa"


def test_normalizar_vazio():
    assert normalizar("") == ""


def test_sem_autor_remove_parentese_final():
    assert sem_autor("Ageratum conyzoides (L.)") == "Ageratum conyzoides"
    assert sem_autor("Uncinula necator") == "Uncinula necator"


def test_sem_autor_nao_remove_parentese_no_meio():
    # parêntese interno (subgênero) não é autor — só o final sai
    assert sem_autor("Praga (Sub) nome (Autor, 1900)") == "Praga (Sub) nome"
