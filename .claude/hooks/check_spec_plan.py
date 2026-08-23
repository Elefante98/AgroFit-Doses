import json, sys

data = json.load(sys.stdin)
path = (
    data.get("tool_input", {}).get("file_path", "")
    or data.get("tool_response", {}).get("filePath", "")
).replace("\\", "/")

if "/docs/superpowers/specs/" in path or "/docs/superpowers/plans/" in path:
    print(json.dumps({
        "systemMessage": (
            "📋 Spec/plano alterado. Antes de avancar: rode o agente `spec-reviewer`; "
            "conserte os bloqueantes; re-rode. Minimo 2 rodadas, e so avance quando uma "
            "rodada voltar SEM bloqueante. Confirme multi-tenant e os 10 pontos de "
            "seguranca explicitos. Checklist: .claude/checklists/spec-plan.md"
        )
    }))
