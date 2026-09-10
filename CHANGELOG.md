# Changelog

Todas as mudanças notáveis deste serviço são documentadas neste arquivo. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Toda feature que altera este
serviço adiciona uma entrada em `[Unreleased]` — verificado automaticamente pela pipeline de CI
(ver `docs/CI-CD.md`).

## [Unreleased]

### Fixed

- Chave do projeto no SonarCloud corrigida para `eimmig_sv-telegram-integration-backend`. O SonarCloud gera a chave como
  `<org>_<repo>` ao importar um repositório do GitHub; a forma sem prefixo, usada até aqui, faria a
  análise falhar com projeto inexistente.
- [SV-181](https://stakevault.atlassian.net/browse/SV-181) - Setup do projeto Python + webhook n8n
- [SV-182](https://stakevault.atlassian.net/browse/SV-182) - Bootstrap uv (pyproject.toml/uv.lock reais) + app FastAPI com GET /health + testes
- [SV-183](https://stakevault.atlassian.net/browse/SV-183) - i18n: locales/{pt-BR,en-US,es}.json + loader com fallback + testes
- [SV-184](https://stakevault.atlassian.net/browse/SV-184) - n8n/telegram-bot.json (webhook + normalizacao) + correcao do gap RabbitMQ/n8n em OBSERVABILITY-AND-CONFIG.md + CHANGELOG e verificacao final
- [SV-185](https://stakevault.atlassian.net/browse/SV-185) - Parsing de mensagens nao estruturadas
- [SV-186](https://stakevault.atlassian.net/browse/SV-186) - Cliente Redis + modulo de estado de conversa (get/set/clear, TTL) + testes com testcontainers
- [SV-187](https://stakevault.atlassian.net/browse/SV-187) - Modulo OCR (pytesseract) + modulo de extracao heuristica (odd/stake/data tipados, nomes brutos best-effort) + testes
- [SV-188](https://stakevault.atlassian.net/browse/SV-188) - Endpoint FastAPI de orquestracao (funde extracao + estado pendente, pergunta campo faltante ou retorna completo) + chaves i18n novas + extensao do n8n workflow (download de foto) + testes
- [SV-189](https://stakevault.atlassian.net/browse/SV-189) - CHANGELOG e verificacao final
- [SV-190](https://stakevault.atlassian.net/browse/SV-190) - Correcao pos-fechamento: extracao validada contra 5 bilhetes reais (usuario forneceu amostras)
- [SV-191](https://stakevault.atlassian.net/browse/SV-191) - RF05 (suporte) - Fluxo de vinculo de conta Telegram
- [SV-192](https://stakevault.atlassian.net/browse/SV-192) - Cliente HTTP direto para auth-service (auth_client.py) + X-Correlation-Id + testes
- [SV-193](https://stakevault.atlassian.net/browse/SV-193) - Endpoint POST /telegram/link + chaves i18n novas + testes (5 outcomes x locales)
- [SV-194](https://stakevault.atlassian.net/browse/SV-194) - n8n (roteamento /vincular) + docs (telegram-integration.md, API-CONTRACTS.md, DECISIONS-LOG.md) + CHANGELOG e verificacao final
- [SV-197](https://stakevault.atlassian.net/browse/SV-197) - RF05 - Integracao com POST /api/v1/bets via api-gateway
- [SV-198](https://stakevault.atlassian.net/browse/SV-198) - catalog_client.py (GET paginado sports/leagues/markets/betting-houses via api-gateway) + testes
- [SV-199](https://stakevault.atlassian.net/browse/SV-199) - PendingBet com fase de catalogo (snapshot de opcoes) + orchestration.py (fuzzy match betting_house, pergunta numerada sport/league/market, catalogo vazio) + chaves i18n novas + testes
- [SV-200](https://stakevault.atlassian.net/browse/SV-200) - bets_client.py (POST /api/v1/bets, conversao de bet_date pra Instant, Idempotency-Key via update_id) + n8n (telegramUpdateId) + mapeamento de outcomes + chaves i18n + testes
- [SV-201](https://stakevault.atlassian.net/browse/SV-201) - CHANGELOG, verificacao final e revisao do vault (docs/services/telegram-integration.md, n8n/README.md - risco residual do update_id)
- [SV-202](https://stakevault.atlassian.net/browse/SV-202) - Pipeline de CI (GitHub Actions + SonarCloud)
- [SV-203](https://stakevault.atlassian.net/browse/SV-203) - Retrofit do gate de qualidade (qualitygate.wait + zero issue) no ci.yml
- [SV-204](https://stakevault.atlassian.net/browse/SV-204) - CHANGELOG, verificacao final e revisao do vault
- [SV-205](https://stakevault.atlassian.net/browse/SV-205) - Checklist de validacao pre-deploy
- [SV-206](https://stakevault.atlassian.net/browse/SV-206) - Validar n8n/telegram-bot.json contra instancia n8n real (local, efemera)
- [SV-207](https://stakevault.atlassian.net/browse/SV-207) - bet_date em America/Sao_Paulo + reconfirmar residuais de auth/rate-limit
- [SV-208](https://stakevault.atlassian.net/browse/SV-208) - CHANGELOG, verificacao final e fechamento de epic-005
- [SV-284](https://stakevault.atlassian.net/browse/SV-284) - Dockerfile para imagem de producao
- [SV-285](https://stakevault.atlassian.net/browse/SV-285) - Dockerfile multi-stage (uv + tesseract-ocr) + verificacao real do container contra a infra
- [SV-290](https://stakevault.atlassian.net/browse/SV-290) - Autenticacao X-Service-Key + limite de corpo em POST /bets/capture e /telegram/link
- [SV-291](https://stakevault.atlassian.net/browse/SV-291) - require_service_key (FastAPI dependency) + BodySizeLimitMiddleware + testes + workflow n8n + docs
- [SV-331](https://stakevault.atlassian.net/browse/SV-331) - CI: build e push da imagem Docker pro GHCR
- [SV-332](https://stakevault.atlassian.net/browse/SV-332) - Job build-and-push-image no ci.yml
- [SV-333](https://stakevault.atlassian.net/browse/SV-333) - CHANGELOG e verificacao final
