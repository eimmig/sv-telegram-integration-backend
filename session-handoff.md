# Session Handoff — telegram-integration

## Current Objective

- Goal: `epic-005` (telegram-integration) — `feat-001` (bootstrap) e `feat-002` (parsing) entregues.
  3 features restam (`feat-003` vínculo de conta, `feat-004` integração com `api-gateway`,
  `feat-005` CI).
- Current status: `feat-001`/`feat-002` `done`, merged into `develop`.
- Branch / commit: `develop` @ `18df1dc` (merge of `feature/SV-185`).

## Completed This Session

- [x] `feat-001` (bootstrap uv + FastAPI + i18n + n8n workflow) — ver entrada anterior deste log
      para o detalhe completo (achados de sequenciamento de CI, SonarCloud, `resolve_locale`).
- [x] **`feat-002` (parsing de mensagens não estruturadas) implementado e mergeado em `develop`**
      — 4 subtasks (SV-186..189, story SV-185), 4 PRs de subtask + 1 PR de story, todos com CI
      real e verde (Tesseract instalado no runner, Redis via testcontainers rodando de verdade).
      Ver `progress.md` para o detalhe completo.
- [x] **Decisão de produto tomada com o usuário via `AskUserQuestion`** (nenhuma nota fixava o
      formato antes): usuário pode enviar **foto do bilhete (OCR) ou texto livre**; motor de OCR
      = **Tesseract local**, não API de nuvem. Registrado em `docs/DECISIONS-LOG.md` 2026-09-08.
- [x] **2 achados reais MAJOR do Plan Review**, corrigidos antes de codificar: escopo reduzido
      pra não resolver nomes extraídos contra o catálogo de `bets-service` (que exige UUID, não
      nome — fica pra `feat-004`); download de foto movido pro n8n em vez do Python (evita
      `TELEGRAM_BOT_TOKEN` como segredo novo aqui — n8n já tem a credencial do Telegram).
- [x] **2 achados reais encontrados durante a implementação/revisão**: caminho de resposta
      direta a uma pergunta armazenava texto cru sem normalizar (data em formato errado) —
      corrigido com `parse_direct_answer`; Delivery Reviewer encontrou dict de campos esparso no
      fluxo multi-turno (formato inconsistente com extração de mensagem única) — corrigido em
      `_merge`, pego só depois de um teste novo ponta a ponta pela HTTP real ser escrito (os
      testes de `orchestration.py` sozinhos não expunham o bug).
- [x] Ambiente de desenvolvimento: Tesseract 5.5.0 instalado (via `winget`, já estava instalado
      mas fora do PATH) + `tessdata` `por`/`eng` baixados pra `~/.local/tessdata` (Program Files
      é read-only sem admin) + `TESSDATA_PREFIX`/`TESSERACT_CMD` — ver `docs/CONVENTIONS.md`.

## Verification Evidence

| Check | Command | Result | Notes |
|---|---|---|---|
| Build/test | `uv run pytest --cov --cov-fail-under=80` | 45 tests, 0 failures, 100% coverage | |
| Local harness | `./init.sh` | pass | service + root (precisa `TESSDATA_PREFIX`/`TESSERACT_CMD` no ambiente) |
| CI (subtask gates) | GitHub Actions | pass | 4 PRs, real execution (Tesseract + Redis testcontainers) |
| CI (full gate) | GitHub Actions + SonarCloud | pass | verde de primeira |
| Delivery Reviewer | review-suite skill | PASS | 1 real finding fixed (dict esparso multi-turno) |
| Test Suite Auditor | codebase-audit-suite skill | PASS | |

## Decisions Made

- Formato de captura: foto do bilhete (OCR) OU texto livre — decisão do usuário.
- OCR: Tesseract local via `pytesseract`, não API de nuvem — decisão do usuário (sem custo, sem
  segredo, sem dependência de rede externa).
- Extração heurística genérica (sem template por casa de apostas, sem amostra real disponível) —
  só `odd`/`stake`/`bet_date` (padrão léxico universal) e `betting_house` (lista curta de casas
  conhecidas) são extraídos com confiança real; `sport`/`league`/`market`/`team1`/`team2`
  **sempre `None`**, nunca "chutados" — campo não resolvido cai no fallback conversacional.
- Estado da conversa no Redis já provisionado em `infra/` (mesma instância de `stats-service`).
- Download de foto fica no n8n (credencial do Telegram nunca sai de lá); Python só recebe base64.
- `feat-002` produz campos **brutos**, não um payload pronto pra `bets-service` — resolver nomes
  contra o catálogo do tenant (IDs) é `feat-004`.

## Blockers / Risks

- Nenhum aberto. `n8n/telegram-bot.json` tem 4 pontos não validados contra instância real
  (documentados em `n8n/README.md`) — não bloqueante, revisitar antes de produção.
- `POST /bets/capture` sem autenticação própria e sem limite de tamanho de corpo pro base64 da
  foto — aceitável no estágio atual (rede local/interna, serviço não containerizado/exposto),
  revisitar quando containerizado.

## Next Session Startup

1. Read `../../CLAUDE.md` e `../../docs/services/telegram-integration.md`.
2. Read this directory's `CLAUDE.md`, `feature_list.json`, `progress.md`.
3. Run `./init.sh` — exportar `TESSDATA_PREFIX=~/.local/tessdata` e
   `TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"` se o terminal não tiver o PATH
   persistido ainda (deveria pegar sozinho após reiniciar o terminal).
4. `Plan Reviewer` antes de codificar `feat-003` (vínculo de conta Telegram) — única feature
   elegível agora (`feat-004` depende dela).

## Recommended Next Step

- `feat-003` (fluxo de vínculo de conta Telegram, `/vincular <codigo>`) é o próximo natural —
  sem ele, `feat-004` (integração real com `POST /api/v1/bets`) não tem como resolver
  `telegramUserId -> userId/tenantId` de verdade.
