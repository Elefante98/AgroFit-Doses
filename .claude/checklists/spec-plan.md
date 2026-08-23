# Gate de spec/plano

Toda spec (`docs/superpowers/specs/`) e plano (`docs/superpowers/plans/`) passa por isto antes de avançar para implementação.

## Rodada de review (obrigatória)

1. Rode o agente **`spec-reviewer`** sobre o artefato.
2. Conserte os achados **bloqueantes de avanço**.
3. Re-rode. **Mínimo 2 rodadas**, e só avance quando uma rodada voltar **sem bloqueante**.

## Multi-Tenant (se o projeto for multi-tenant)

- A spec/plano **explicita** como cada feature preserva o isolamento entre tenants (quem pode ler/escrever qual recurso).
- Inclui **testes automatizados de autorização** (acesso cross-tenant deve dar 403/404) como parte do plano — não como "depois".

## Segurança

- Passe pelos **10 pontos** em `.claude/checklists/security-10.md`. Para cada um relevante, a abordagem está na spec e há teste onde couber.

## Qualidade de código (herda para o plano)

- Reaproveitar em vez de duplicar.
- Sem código morto no fim (ambiente limpo é regra).
