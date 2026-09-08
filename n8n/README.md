# Fluxo n8n — StakeVault Bot

`telegram-bot.json` é o workflow exportado (formato nativo do n8n) que recebe o webhook do
Telegram, resolve foto ou texto, e chama o serviço Python:

1. **Telegram Trigger** — dispara em toda mensagem recebida pelo bot.
2. **Has photo?** (nó `IF`) — ramifica conforme a mensagem trazer `message.photo` ou não.
3. **Get photo file** (nó `Telegram`, `resource: file`/`operation: get`, `download: true`) —
   baixa a maior resolução da foto (último item do array `message.photo`) usando a mesma
   credencial já configurada no Trigger — o serviço Python nunca vê o token do bot (decisão de
   `feat-002`, ver `docs/DECISIONS-LOG.md` 2026-09-08).
4. **Normalize photo payload** / **Normalize text payload** (nós `Set`) — extraem
   `telegramUserId`, `languageCode`, `chatId` e (conforme o ramo) `photoBase64` ou `text`, num
   formato plano. Os dois convergem no mesmo nó seguinte.
5. **Capture bet (Python)** (nó `HTTP Request`) — `POST /bets/capture` no serviço Python
   (`feat-002`), corpo JSON com os campos normalizados.
6. **Send reply** (nó `Telegram`, `sendMessage`) — responde ao usuário com `message` da resposta
   do Python (pergunta de campo faltante, ou confirmação de captura) — o Python sempre devolve
   `chatId`/`message`, então este nó não precisa referenciar nó nenhum anterior.

## Escopo (feat-002) vs próximos passos

Este workflow chama o serviço Python de verdade agora, mas **não resolve nome de casa de
apostas/esporte/liga/mercado contra o catálogo do tenant nem registra a aposta** — isso é
`feat-004` (a resposta "complete" do Python só devolve os campos extraídos brutos, não um
`POST /api/v1/bets` pronto). A URL do `HTTP Request` (`http://localhost:8000/bets/capture`) é
placeholder de desenvolvimento local — vira variável de ambiente/configuração do n8n quando este
serviço for containerizado (fora do escopo de `feat-002`).

## Risco residual (registrado nos Plan Reviews de feat-001 e feat-002)

Este JSON foi montado a partir da estrutura de export documentada do n8n (nós `nodes[]`/
`connections{}`, campos `type`/`typeVersion`/`position`/`parameters`), não exportado de uma
instância real rodando — `docs.n8n.io/workflows/export-import` retornou 404 no momento da
pesquisa, então o grounding veio de fonte secundária (confirmado: tipo do nó Telegram Trigger,
formato geral de `Set`, existência do recurso `file`/operação `get` do nó `Telegram` com os
parâmetros `fileId`/`download`). **Antes de usar em produção, importar este arquivo numa
instância n8n real e confirmar**, em ordem de risco:

1. **`{{$binary.data.data}}`** (nó "Normalize photo payload") — a expressão exata para acessar o
   conteúdo binário baixado como base64 varia entre versões do n8n; não verificada contra uma
   instância real.
2. O schema de `conditions` do nó `IF` (`has-photo`) — usado aqui o formato mais antigo/simples
   (`conditions.string[]`), que pode ter sido substituído pelo formato v2
   (`conditions.combinator`/`conditions.conditions[]`) em versões recentes do n8n.
3. Os nomes exatos dos parâmetros do nó `Telegram` (`resource`/`operation`/`fileId`/`download`)
   — confirmados na documentação oficial só como rótulos de UI, não como chaves JSON.
4. `parameters.values.string` do nó `Set` (já sinalizado desde `feat-001`).
