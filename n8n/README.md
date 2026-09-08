# Fluxo n8n — StakeVault Bot

`telegram-bot.json` é o workflow exportado (formato nativo do n8n) que recebe o webhook do
Telegram, ramifica entre vínculo de conta, foto e texto, e chama o serviço Python:

1. **Telegram Trigger** — dispara em toda mensagem recebida pelo bot.
2. **Is /vincular command?** (nó `IF`, `startsWith` sobre `message.text`) — ramifica antes de
   qualquer outra coisa: mensagem começando com `/vincular ` segue pro fluxo de vínculo de conta
   (`feat-003`); qualquer outra mensagem (foto ou texto livre) segue pro fluxo de captura de
   aposta já existente (`feat-002`), inalterado.
3. **Normalize link payload** (nó `Set`, ramo `/vincular`) — extrai `telegramUserId`,
   `languageCode`, `chatId` e `code` (segundo token do texto, após o espaço — `/vincular
   ABCD1234` → `code = "ABCD1234"`).
4. **Confirm link (Python)** (nó `HTTP Request`) — `POST /telegram/link` no serviço Python
   (`feat-003`), corpo JSON com os campos normalizados. Resposta sempre `{message, chatId}`,
   mesmo formato do fluxo de captura — converge no mesmo nó **Send reply** do passo 8.
5. **Has photo?** (nó `IF`, ramo não-`/vincular`) — ramifica conforme a mensagem trazer
   `message.photo` ou não.
6. **Get photo file** (nó `Telegram`, `resource: file`/`operation: get`, `download: true`) —
   baixa a maior resolução da foto (último item do array `message.photo`) usando a mesma
   credencial já configurada no Trigger — o serviço Python nunca vê o token do bot (decisão de
   `feat-002`, ver `docs/DECISIONS-LOG.md` 2026-09-08).
7. **Normalize photo payload** / **Normalize text payload** (nós `Set`) — extraem
   `telegramUserId`, `languageCode`, `chatId`, `telegramUpdateId` (`feat-004`, ver abaixo) e
   (conforme o ramo) `photoBase64` ou `text`, num formato plano. Os dois convergem no mesmo nó
   seguinte.
8. **Capture bet (Python)** (nó `HTTP Request`) — `POST /bets/capture` no serviço Python
   (`feat-002`/`feat-004`), corpo JSON com os campos normalizados.
9. **Send reply** (nó `Telegram`, `sendMessage`) — responde ao usuário com `message` da resposta
   do Python (confirmação/erro de vínculo, pergunta de campo faltante, ou confirmação de
   captura) — todo endpoint Python sempre devolve `chatId`/`message`, então este nó não precisa
   referenciar nó nenhum anterior, seja qual for o ramo percorrido.

## Escopo (feat-002/feat-003/feat-004) vs próximos passos

Este workflow chama o serviço Python de verdade e (`feat-004`) o Python agora resolve o catálogo
do tenant e registra a aposta de verdade em `bets-service` via `api-gateway`. `feat-003` não gera
o código de vínculo (isso é responsabilidade de `apps/web`, `epic-006`) — só confirma um código já
existente. As URLs dos nós `HTTP Request` (`http://localhost:8000/bets/capture`,
`http://localhost:8000/telegram/link`) são placeholder de desenvolvimento local — viram variável
de ambiente/configuração do n8n quando este serviço for containerizado (fora do escopo de
`feat-002`/`feat-003`/`feat-004`).

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
2. O schema de `conditions` do nó `IF` (`has-photo`, `is-link-command`) — usado aqui o formato
   mais antigo/simples (`conditions.string[]`), que pode ter sido substituído pelo formato v2
   (`conditions.combinator`/`conditions.conditions[]`) em versões recentes do n8n. O campo
   `operation: "startsWith"` do nó novo `is-link-command` (`feat-003`) segue o mesmo risco —
   nome exato da operação não confirmado contra uma instância real.
3. Os nomes exatos dos parâmetros do nó `Telegram` (`resource`/`operation`/`fileId`/`download`)
   — confirmados na documentação oficial só como rótulos de UI, não como chaves JSON.
4. `parameters.values.string` do nó `Set` (já sinalizado desde `feat-001`) — inclui o `Normalize
   link payload` novo (`feat-003`), com a mesma ressalva pro método `.split(\" \")[1]` usado ali
   (sintaxe JS padrão, mas o contexto de expressão do n8n em torno dela não foi validado contra
   uma instância real).
5. **`{{$json["update_id"]}}`** (nós "Normalize text/photo payload", `feat-004`) — assume que o
   payload bruto do Telegram Trigger tem `update_id` como campo de nível superior, irmão de
   `message` (formato padrão da Bot API do Telegram), nunca referenciado neste workflow até
   agora (todos os campos anteriores vêm de dentro de `message.*`). Usado como base do
   `Idempotency-Key` da chamada `POST /api/v1/bets` (protege contra reenvio do mesmo webhook pelo
   Telegram) — se o campo estiver em outro nível na instância real, a chave de idempotência vira
   `None`/vazia silenciosamente; revisitar junto com o item 1 ao validar contra uma instância real.
