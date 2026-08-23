# 10 pontos de segurança — momento de atenção

Passe por estes 10 ao escrever/revisar uma spec ou plano. Para cada um: a feature toca nisso? Se sim, a spec explicita a abordagem **e** (onde der) um teste automatizado?

1. **Isolamento multi-tenant / IDOR** — autorização a nível de objeto em toda rota (o recurso pertence ao tenant do requisitante?). Ver `.claude/checklists/spec-plan.md` → bloco Multi-Tenant.
2. **Autenticação & sessão** — token/sessão, rotação de refresh, lockout, anti-timing no login.
3. **Validação & injeção** — SQLi (uso correto do ORM), fórmula em planilha (sanitize), header injection.
4. **Controle de acesso por role** — menor privilégio por endpoint; gate de role na borda.
5. **Upload seguro** — whitelist de tipo/tamanho, content-type, path traversal, chave de storage previsível.
6. **Segredos & config** — chave secreta forte, flags de ambiente (prod/cookie secure), nada hardcoded.
7. **Rate limiting / DoS** — endpoints de auth e limite global.
8. **Erros & vazamento** — sem stack trace, erro genérico, sem enumeração de usuário.
9. **Exposição de dados** — logs sem PII, audit log, headers de segurança / HSTS.
10. **Dependências & supply chain** — pins no lockfile, atenção a vuln conhecida.

> Nem tudo é testável — priorize testes em 1, 2 e 4. Onde não houver teste, deixe o risco **explícito** na spec.
