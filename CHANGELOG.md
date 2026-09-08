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
