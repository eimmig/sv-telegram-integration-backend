# Session Handoff — telegram-integration

## Current Objective

- Goal: `epic-005` (telegram-integration) — `feat-001` (bootstrap) e `feat-002` (parsing)
  entregues. 3 features restam (`feat-003` vínculo de conta, `feat-004` integração com
  `api-gateway`, `feat-005` CI).
- Current status: `feat-001`/`feat-002` `done`, merged into `develop`.
- Branch / commit: `develop` @ `9cb177d` (merge of `feature/SV-185`, segunda vez — `feat-002.5`).

## Completed This Session

- [x] `feat-001` (bootstrap uv + FastAPI + i18n + n8n workflow) — ver entrada anterior deste log
      para o detalhe completo.
- [x] `feat-002` (parsing de mensagens não estruturadas, OCR + fallback conversacional) — ver
      entrada anterior deste log para o detalhe completo (decisões de produto, achados MAJOR do
      Plan Review, achados de implementação).
- [x] **`feat-002.5` (correção pós-fechamento, reabertura no mesmo dia): extração validada contra
      5 bilhetes reais que o usuário forneceu localmente** (não commitados — dados de
      aposta/financeiro). Rodei OCR de verdade (não só leitura visual) contra as 5 amostras — 2
      achados reais confirmados e corrigidos:
      1. Odd bare-scan podia capturar um valor de moeda (R$) em vez da odd real — corrigido
         excluindo valores de moeda do escaneio antes de buscar a odd.
      2. `bet_date` era extraído de qualquer padrão dd/mm/aaaa, mas o bilhete normalmente mostra
         a data do **evento**, não da aposta (confirmado em 2/5 amostras reais) — dado errado
         silencioso, pior que campo ausente. Removido por completo; `orchestration.py` agora
         sempre usa a data de hoje quando ausente; campo saiu de `REQUIRED_FIELDS`.
      Testado `--psm 6` do Tesseract como alternativa pra 2 casos que ainda falham — rejeitado
      por piorar silenciosamente o stake de outra amostra (erro de 100x). Ver `progress.md` para
      o resultado completo (stake 5/5 correto, odd 2/5 correto + 3/5 caem no fallback com
      segurança).
- [x] Ambiente de desenvolvimento: Tesseract 5.5.0 instalado (via `winget`) + `tessdata`
      `por`/`eng` baixados pra `~/.local/tessdata` + `TESSDATA_PREFIX`/`TESSERACT_CMD` — ver
      `docs/CONVENTIONS.md`.

## Verification Evidence

| Check | Command | Result | Notes |
|---|---|---|---|
| Build/test | `uv run pytest --cov --cov-fail-under=80` | 45 tests, 0 failures, 100% coverage | |
| Local harness | `./init.sh` | pass | service + root (precisa `TESSDATA_PREFIX`/`TESSERACT_CMD` no ambiente) |
| CI (subtask gates) | GitHub Actions | pass | real execution (Tesseract + Redis testcontainers) |
| CI (full gate) | GitHub Actions + SonarCloud | pass | verde de primeira, nas duas rodadas (`feat-002` e `feat-002.5`) |
| Delivery Reviewer | review-suite skill | PASS | achados reais fixados nas duas rodadas |
| Test Suite Auditor | codebase-audit-suite skill | PASS | |
| Validação manual contra dados reais | OCR + `extract_fields` contra 5 bilhetes reais | stake 5/5, odd 2/5 + fallback seguro nos outros 3/5 | não commitado, ver `progress.md` |

## Decisions Made

- Formato de captura: foto do bilhete (OCR) OU texto livre — decisão do usuário.
- OCR: Tesseract local via `pytesseract`, não API de nuvem — decisão do usuário.
- Extração heurística genérica (sem template por casa de apostas) — só `odd`/`stake` (padrão
  léxico universal) e `betting_house` (lista curta de casas conhecidas) são extraídos com
  confiança real; `sport`/`league`/`market`/`team1`/`team2` **sempre `None`**.
- **`bet_date` não é extraído de texto** (mudou nesta sessão) — bilhete mostra tipicamente a data
  do evento, não da aposta; `orchestration.py` sempre usa a data de hoje (UTC, servidor) quando
  ausente. Único campo que não passa por `REQUIRED_FIELDS`/fallback conversacional.
- Estado da conversa no Redis já provisionado em `infra/` (mesma instância de `stats-service`).
- Download de foto fica no n8n (credencial do Telegram nunca sai de lá); Python só recebe base64.
- `feat-002` produz campos **brutos**, não um payload pronto pra `bets-service` — resolver nomes
  contra o catálogo do tenant (IDs) é `feat-004`.
- Imagens reais de bilhete que o usuário forneceu **não foram commitadas** no repositório (dados
  de aposta/financeiro) — usadas só para validação manual nesta sessão.

## Blockers / Risks

- Nenhum aberto. `n8n/telegram-bot.json` tem 4 pontos não validados contra instância real
  (documentados em `n8n/README.md`) — não bloqueante, revisitar antes de produção.
- `POST /bets/capture` sem autenticação própria e sem limite de tamanho de corpo pro base64 da
  foto — aceitável no estágio atual (rede local/interna, serviço não containerizado/exposto).
- `bet_date` usa data UTC, não horário de Brasília — possível off-by-one perto da meia-noite BRT.
  Aceito (nenhuma convenção de timezone existe no projeto pra violar).
- Extração de odd falha (cai no fallback) pra bilhetes com odd em texto colorido/riscado (boost)
  ou layout em coluna que o OCR reordena — limitação real confirmada, aceita, não perseguida com
  mais heurística (risco de overfitting a uma amostra).

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
