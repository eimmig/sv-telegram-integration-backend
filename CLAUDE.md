# CLAUDE.md — telegram-integration

Captura automática de apostas via bot do Telegram. Python 3.12+ e n8n. Parte do harness
multinível do monorepo — leia `../../CLAUDE.md` (raiz) para invariantes cross-service antes
deste arquivo, e `../../docs/services/telegram-integration.md` para o desenho completo.
Ferramentas Python, testes e formato de chamada ao `bets-service` são normativos e já
decididos em `../../docs/CONVENTIONS.md`, `../../docs/TESTING.md` e
`../../docs/API-CONTRACTS.md` — leia-os antes de `feat-001`.

## Fluxo de início de sessão (Startup Workflow)

1. Confirme o diretório de trabalho (`pwd`) — deve ser `services/telegram-integration`.
2. Leia `../../CLAUDE.md` e `../../docs/services/telegram-integration.md`.
3. Rode `./init.sh` para verificar dependências/testes deste serviço.
4. Leia `feature_list.json` (deste serviço) para a próxima feature granular.
5. Leia `progress.md` (deste serviço).

## Regras específicas deste serviço

- **Uma feature por vez (One feature at a time)**: escolha exatamente uma feature `not-started`
  de `feature_list.json` cujas dependências já estejam `done`.
- **Escopo restrito (stay in scope)**: não edite código de `bets-service` a partir desta pasta.
- **uv** para dependências (`pyproject.toml`) e **ruff** para lint/format — decisão já tomada
  em `../../docs/CONVENTIONS.md`, não reabrir. `mypy` roda como parte de `./init.sh`.
- Isolamento de falhas é a razão de este serviço existir separado dos serviços Java — não
  reescreva em Java "para unificar a stack" (ver `../../docs/ARCHITECTURE.md`).
- Chama `POST /api/v1/bets` **através do `services/api-gateway`** (não diretamente no
  `bets-service`), autenticando com header `X-Service-Key` (credencial de serviço, não token
  PASETO — não há usuário logado neste fluxo) e com header `Idempotency-Key` (ver
  `../../docs/API-CONTRACTS.md`) — não crie um endpoint alternativo lá, e não duplique regras
  de negócio (validação de odd/stake) aqui: valide o formato da mensagem, mas deixe
  RN02/RN03/RN06/RN07 para o `bets-service` aplicar. Campo `status` enviado sempre em inglês
  (`pending`/`won`/`lost`/`void` — ver `../../docs/API-CONTRACTS.md`).
- Antes de capturar qualquer aposta, o `telegramUserId` precisa ter um vínculo confirmado com um
  usuário (`TELEGRAM_ACCOUNT` em `auth-service`) — ver `feat-003`. Um `401` do `api-gateway`
  nessa chamada normalmente significa "sem vínculo", não uma falha de infraestrutura.
  > **Resolvido em 2026-08-02** (ver `../../docs/DECISIONS-LOG.md` item 15): o lookup
  > `telegramUserId -> userId`/`tenantId` em `auth-service` consulta um diretório `TELEGRAM_LINK`
  > no schema `public` (fora de qualquer schema de tenant) — resolve direto, sem o bot precisar
  > informar o slug do tenant.
- Propague `X-Correlation-Id` na chamada ao `api-gateway` (ver
  `../../docs/OBSERVABILITY-AND-CONFIG.md`).
- **i18n**: mensagens que o bot envia de volta ao usuário (erro de vínculo, confirmação de
  aposta capturada, etc.) são localizadas (`pt-BR`/`en-US`/`es`, sempre os três) a partir do
  campo `language_code` que o próprio update do Telegram já traz — ver
  `../../docs/CONVENTIONS.md` seção "Internacionalização (i18n)". Nenhuma mensagem do bot é
  hardcoded num idioma só. Formato **JSON**, um arquivo por locale em
  `locales/{pt-BR,en-US,es}.json` (decisão fechada em 2026-08-02, ver
  `../../docs/DECISIONS-LOG.md`) — validado automaticamente pela pipeline de CI (bullet abaixo).
- Fluxos do n8n (webhook do Telegram → normalização → chamada ao script Python) devem ser
  exportados como JSON versionado neste diretório (ex.: `n8n/telegram-bot.json`), não deixados
  apenas na instância online do n8n.
- **CI/CD (`feat-005`)**: pipeline em `.github/workflows/ci.yml`, **dentro deste repositório**
  (este serviço é seu próprio repositório Git, não um monorepo — ver
  `../../docs/DECISIONS-LOG.md` "Topologia") — changelog, i18n, build (`uv sync` + `ruff
  check`), testes (`pytest --cov`), SonarCloud. Scripts de validação em `.github/scripts/`
  (duplicados aqui, não compartilhados com os outros serviços). Ver `../../docs/CI-CD.md`. Toda
  feature adiciona uma entrada em `CHANGELOG.md` deste serviço (verificado automaticamente pelo
  CI quando este repositório existir no GitHub).
- **Skills de agente prioritárias**: `Plan Reviewer` antes de codificar, `Delivery Reviewer` +
  `Test Suite Auditor` antes de marcar `done` (claude-code-skills) — mapeamento completo em
  `../../docs/AGENT-SKILLS.md`. Instaladas em 2026-08-02 (escopo `user`), ver
  `../../docs/DECISIONS-LOG.md`.

## Definição de pronto (Definition of Done)

Uma feature deste serviço só está `done` quando (done only when):

> **Antes de começar** (não é item de `done`, é pré-requisito de `in-progress`): o campo
> `plan_review` daquela feature em `feature_list.json` precisa estar preenchido com o
> resultado do `Plan Reviewer` — ver `CLAUDE.md` da raiz, seção "Regras de trabalho".


- [ ] Implementada e rodando via `./init.sh` sem erro (pytest + cobertura ≥ 80%, ver
      `../../docs/TESTING.md`).
- [ ] Testes de parsing cobrindo mensagens bem formadas e malformadas, com chamadas externas
      mockadas (Telegram/n8n).
- [ ] Se a feature envia mensagem ao usuário: teste confirmando que o texto muda conforme
      `language_code` simulado (pelo menos dois dos três locales).
- [ ] `Delivery Reviewer` e `Test Suite Auditor` rodados contra a feature (ver
      `../../docs/AGENT-SKILLS.md`).
- [ ] `CHANGELOG.md` deste serviço tem uma entrada em `[Unreleased]` descrevendo a mudança.
- [ ] `feature_list.json` atualizado com status e evidência.
- [ ] `../../feature_list.json` (raiz) atualizado se este foi o marco que fecha `epic-005`.

## Fim de sessão (End of Session)

Antes de encerrar (before ending a session): atualize `progress.md` deste serviço, atualize
`feature_list.json`, e deixe `./init.sh` passando (clean, restartable state) — stay in scope:
não edite código de `bets-service` aqui, apenas consuma o endpoint dele.

## Verificação

```bash
./init.sh
```
