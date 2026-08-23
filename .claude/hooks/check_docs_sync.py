import json, sys

data = json.load(sys.stdin)
path = (
    data.get("tool_input", {}).get("file_path", "")
    or data.get("tool_response", {}).get("filePath", "")
).replace("\\", "/")

is_spec_plan = "/docs/superpowers/specs/" in path or "/docs/superpowers/plans/" in path
# hot.md/index.md da wiki mudam TODA sessao (bookkeeping de End Session) — excluir
# p/ nao gerar nudge a cada fim de sessao.
is_wiki_churn = path.endswith("/hot.md") or path.endswith("/index.md")
touches_docs = ("/docs/" in path or "/.claude/wiki/" in path)
if touches_docs and not is_spec_plan and not is_wiki_churn:
    print(json.dumps({
        "systemMessage": (
            "🔄 docs/wiki alterados. Avalie se o CLAUDE.md raiz precisa refletir a "
            "mudanca (estado vigente, convencoes, endpoints). Se sim, atualize junto."
        )
    }))
