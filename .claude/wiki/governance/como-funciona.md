# Governança da Wiki — AgroFit Doses

> Como esta wiki funciona.

## Estrutura

```
.claude/wiki/
├─ hot.md         # estado atual (ler 1º no Bootstrap)
├─ index.md       # mapa do grafo (ler 2º)
├─ raw/           # caixa de entrada de sessões — processa, nunca deleta
├─ projects/      # tasks (AGD-NNN)
├─ areas/<area>/
│  ├─ concepts/   # notas atômicas (uma ideia por arquivo)
│  └─ decisions/  # ADRs (ADR-NNN)
├─ core/          # conhecimento transversal
└─ governance/    # este diretório — como a wiki funciona
```

## Regras

1. **hot.md e index.md são sagrados.** Sempre atualizados no End Session.
2. **raw/ é imutável-por-convenção.** Você processa o conteúdo (extrai concepts e ADRs), mas não apaga o registro bruto. Ele é o rastro auditável da sessão.
3. **Toda decisão de arquitetura vira um ADR.** Mudança estrutural sem ADR é dívida técnica.
4. **Notas atômicas.** Um conceito por arquivo em `concepts/`, linkável via `[[ ]]`.
5. **ADRs são numerados e versionados.** Formato `ADR-NNN-titulo-curto.md`.

## Ciclo de uma sessão

`Bootstrap → Check ADR → Code (no ritual) → Update Wiki → End Session`
