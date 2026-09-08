# Fluxo n8n — StakeVault Bot

`telegram-bot.json` é o workflow exportado (formato nativo do n8n) que recebe o webhook do
Telegram e normaliza o payload:

1. **Telegram Trigger** — dispara em toda mensagem recebida pelo bot.
2. **Normalize payload** (nó `Set`) — extrai `telegramUserId`, `languageCode`, `text` e `chatId`
   da mensagem crua do Telegram para um formato plano, mais simples de consumir.

## Escopo (feat-001) vs próximos passos

Este workflow **para na normalização** — não há nó de `HTTP Request` chamando o serviço Python
ainda, porque o endpoint que recebe o JSON normalizado só é criado em `feat-002` (parsing). A
integração real n8n → Python é adicionada naquela feature, não nesta.

## Risco residual (registrado no Plan Review de feat-001)

Este JSON foi montado a partir da estrutura de export documentada do n8n (nós `nodes[]`/
`connections{}`, campos `type`/`typeVersion`/`position`/`parameters`), não exportado de uma
instância real rodando — `docs.n8n.io/workflows/export-import` retornou 404 no momento da
pesquisa, então o grounding veio de fonte secundária. **Antes de usar em produção, importar este
arquivo numa instância n8n real e confirmar que os dois nós carregam sem erro** (especialmente o
formato de `parameters.values.string` do nó `Set`, que pode variar entre versões do n8n).
