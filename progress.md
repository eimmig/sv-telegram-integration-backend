# Log de Progresso — telegram-integration

## Estado Atual (Current State)

**Última atualização:** 2026-09-08
**Feature ativa:** nenhuma (`feat-001` `done`; `feat-002` é a próxima elegível)

## Status

### O que está pronto

- [x] Harness deste serviço criado.
- [x] `feat-001` (Setup do projeto Python + webhook n8n) — `done` em 2026-09-08.

### Em andamento

- Nenhuma feature iniciada.

### Próximos passos (Next Steps)

1. `feat-002` (Parsing de mensagens não estruturadas) — única feature elegível agora.

## `feat-001` fechada — bootstrap uv + FastAPI + i18n + n8n (2026-09-08)

Primeiro serviço Python do backlog — nenhum código existia antes desta sessão. 3 subtasks
(SV-182..184, story SV-181), 3 PRs de subtask (#1, #2, #3) + 1 PR de story (#4, `feature ->
develop`), todos com CI real e verde (execução de verdade — `uv sync`/`ruff`/`mypy`/`pytest --cov`
rodando no runner, não guarda pulada).

**Bootstrap real, não escrito à mão**: `pyproject.toml`/`uv.lock` gerados via `uv init`/`uv add`
de verdade (versões resolvidas do PyPI, mesmo padrão de `start.spring.io` usado em
`api-gateway feat-001`). **FastAPI + Uvicorn** decidido como framework HTTP (nenhuma nota fixava
isso antes) — registrado em `docs/CONVENTIONS.md` (repositório raiz `sv-harness`). `GET /health`
prova o app de pé. i18n (`locales/{pt-BR,en-US,es}.json` + `resolve_locale`/`get_message`, uma
chave real `generic_error`) prova o mecanismo ponta a ponta, mesmo padrão já aceito em
`auth-service feat-001.5`/`api-gateway feat-001.3`. `n8n/telegram-bot.json` (Telegram Trigger +
normalização) exportado parando propositalmente antes do nó `HTTP Request` — a chamada real
n8n → Python fica para `feat-002`, quando o endpoint de parsing existir; risco residual
documentado em `n8n/README.md` (JSON não validado contra instância real de n8n —
`docs.n8n.io/workflows/export-import` retornou 404 durante a pesquisa, grounding via fonte
secundária).

**Impedimento real resolvido antes de codificar**: `uv` não estava instalado nesta máquina —
`Scripts` global do Python é somente leitura sem admin, corrigido via `pip install --user uv` +
cópia do executável para `~/.local/bin` (já no PATH desta sessão, mesmo mecanismo do gotcha
anterior do `claude.exe`) + PATH do usuário persistido via PowerShell para sessões futuras.

**2 achados reais de sequenciamento de CI, corrigidos rodando os PRs de verdade** (mesma
armadilha já documentada em `docs/CI-CD.md` para os outros 6 repositórios, nunca portada para
este até agora): passo de i18n guardado só por `pyproject.toml` quebraria a subtask de bootstrap
antes de `locales/` existir — corrigido para guarda própria por `locales/pt-BR.json`; passo de
changelog rodando em todo PR (não só `story -> develop`) quebrou de verdade a PR da subtask 2
(`CHANGELOG.md` já populado inteiro desde a criação da story via `jira_story.py`, sem diff novo
por subtask) — corrigido para guarda por `base_ref`.

**Achado real de documentação corrigido**: `docs/OBSERVABILITY-AND-CONFIG.md` dizia que o
`/health` deste serviço verifica conectividade com "RabbitMQ/n8n" — nenhuma nota sustentava isso
(o serviço nunca fala com RabbitMQ nem chama n8n, é o contrário). Corrigido na própria nota.

**Delivery Reviewer** (passe próprio): PASS, 1 achado real corrigido antes de fechar —
`resolve_locale` usava `startswith` (um `language_code` de 1 caractere como `"e"` casava por
acidente com `en-US`) — corrigido para comparação exata do subtag de idioma (parte antes do
`-`). **Test Suite Auditor**: PASS — testes provam mapeamento de locale real (parametrizado,
casos de fallback), nenhum teste trivial.

**Achado real do SonarCloud** (PR story → develop, primeira análise de verdade deste
repositório): Security Rating E em "Avoid binding the application to all network interfaces" —
o entrypoint de dev `main()` usava `host="0.0.0.0"`; corrigido para `"127.0.0.1"` (bind em todas
as interfaces só faz sentido num deploy real via Dockerfile/container, decisão de infra futura,
não deste script de conveniência local).

12 testes, 0 falhas, cobertura 100% (gate 80%). `./init.sh` do serviço e da raiz verdes. Libera
`feat-002` (parsing de mensagens); `epic-005` (raiz) continua `in-progress` até `feat-002..005`
também fecharem.

## Bloqueios / Riscos

- Nenhum aberto. Risco residual do `n8n/telegram-bot.json` (não testado contra instância real de
  n8n) documentado em `n8n/README.md`, não bloqueante.

## Harness criado (2026-07-30)

`CLAUDE.md`, `feature_list.json`, `init.sh`, `progress.md`, `session-handoff.md` criados — sem
código de aplicação ainda. Ver `../../docs/services/telegram-integration.md` para o fluxo
completo.
