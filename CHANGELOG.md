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
