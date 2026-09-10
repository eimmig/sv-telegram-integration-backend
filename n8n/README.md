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

## Validado contra instância n8n real (feat-006, 2026-09-08)

Este JSON foi originalmente montado a partir da estrutura de export documentada do n8n, sem
acesso a uma instância real (`docs.n8n.io/workflows/export-import` retornou 404 durante a
pesquisa em `feat-001`) — os 5 pontos abaixo ficaram como risco residual aceito até esta feature.

`infra/docker-compose.yml` já provisiona um serviço `n8n` real (`docker.n8n.io/n8nio/n8n:1.100.0`)
desde `epic-001`, nunca subido localmente até agora. Subido via `docker compose up -d n8n`
(`.env` local não commitado) e validado com evidência direta, sem precisar de bot Telegram real
(nenhum token existe no projeto):

- Importado via `n8n import:workflow --input=telegram-bot.json` (CLI dentro do container) —
  sucesso, sem erro de schema.
- Schema de nós/parâmetros conferido contra `GET /types/nodes.json` (definição real dos node
  types instalados nesta versão) via a API REST do próprio n8n (conta owner local criada só para
  a inspeção, instância efêmera).
- Comportamento de runtime (o que gera cada expressão) conferido lendo o código-fonte real dos
  nodes `Telegram`/`TelegramTrigger` dentro do container (`node_modules/n8n-nodes-base/dist/...`).

Resultado — **os 5 pontos confirmados corretos, nenhuma divergência, nenhuma mudança necessária
no workflow**:

1. **`{{$binary.data.data}}`** — confirmado no código-fonte de `Telegram.node.js`: o download de
   arquivo (`resource: file`/`operation: get`) grava o resultado como
   `binary: { data }` (propriedade binária chamada literalmente `data`), e `prepareBinaryData`
   preenche o campo `.data` daquele objeto com o conteúdo em base64 — `$binary.data.data` é
   exatamente essa cadeia, não uma coincidência de nome.
2. Schema de `conditions` do nó `IF` v1 (`conditions.string[]`) — confirmado ainda registrado e
   suportado em 1.100.0 (`GET /types/nodes.json` lista as versões `1` e `[2, 2.1, 2.2]` como
   variantes coexistentes do mesmo node type, `defaultVersion` 2.2 só afeta nós novos). Operação
   `"startsWith"` confirmada como valor válido do enum `conditions.string[].operation` do node v1.
3. Nomes exatos dos parâmetros do nó `Telegram` confirmados via `GET /types/nodes.json`:
   `resource: "file"` + `operation: "get"` aceita `fileId`/`download`; `resource: "message"` +
   `operation: "sendMessage"` exige `chatId`/`text` (ambos `required: true`).
4. `parameters.values.string` do nó `Set` v1 — confirmado ainda registrado (`version: [1, 2]` no
   node type instalado) e importado sem erro nem transformação. `.split(" ")[1]` é JS padrão,
   sem risco específico do n8n.
5. **`{{$json["update_id"]}}`** — confirmado no código-fonte de `TelegramTrigger.node.js`:
   `webhook()` faz `bodyData = this.getBodyData()` e repassa o corpo bruto da requisição sem
   nenhuma transformação (`returnJsonArray([bodyData])`) — `update_id` chega exatamente como a
   Bot API do Telegram o envia, irmão de `message` no nível raiz.

**Residual que sobrevive** (não dá pra validar sem um bot Telegram real, fora do escopo local):
credencial `telegramApi` (token do BotFather) nunca configurada nem testada contra a API real do
Telegram — o fluxo completo ponta a ponta (mensagem real → webhook → n8n → Python → resposta)
continua não exercitado. Optado por não criar um bot de teste agora (dependência externa
desnecessária pra este checklist); revisitar antes de qualquer usuário real usar o bot em
produção.

## Outros residuais aceitos (reconfirmados em `feat-006`, 2026-09-08)

- **`POST /api/v1/telegram-accounts` em `auth-service` sem rate limiting** (aceito em
  `telegram-integration feat-003`, mitigado por TTL curto do código de vínculo + espaço de busca
  grande) — continua válido: gatilho é `auth-service` exposto além da rede interna, e isso não
  mudou (`infra/feat-004`/Kubernetes deixa esse serviço `ClusterIP`-only, sem `Ingress`).

## `POST /bets/capture`/`POST /telegram/link` sem autenticação — resolvido (`feat-008`, 2026-09-10)

O residual aceito em `feat-002`/`feat-003` ("aceitável só enquanto o serviço roda em rede
local/interna, não containerizado/exposto — revisitar quando este serviço for containerizado")
teve seu gatilho atingido: `infra/feat-004` (migração para Kubernetes) containerizou este
serviço. Resolvido:

- Os dois endpoints agora exigem o header `X-Service-Key` (dependência FastAPI
  `require_service_key`, `services/telegram_integration/main.py`) — **mesmo segredo** já usado
  pelas chamadas de saída deste serviço para `api-gateway` (`bets_client.py`/
  `catalog_client.py`), não um novo. `401` sem o header ou com valor errado.
- `telegram-bot.json`: os 2 nós `HTTP Request` (**Confirm link (Python)**, **Capture bet
  (Python)**) ganharam `authentication: genericCredentialType`/`genericAuthType: httpHeaderAuth`,
  referenciando uma credencial nova (`id: "2"`, `name: "X-Service-Key (StakeVault)"`) — **precisa
  ser criada manualmente na instância do n8n** antes do workflow funcionar (mesmo precedente da
  credencial `telegramApi` `id: "1"`, referenciada mas nunca embutida no JSON exportado, nunca
  configurada nesta sessão por não haver bot real). Ao criar: tipo "Header Auth", nome do header
  `X-Service-Key`, valor = o mesmo `SERVICE_KEY` configurado no `.env` deste serviço.
- Limite de tamanho de corpo (10 MiB, generoso o bastante pra nunca rejeitar uma foto real de
  bot do Telegram) via `BodySizeLimitMiddleware` (`body_size_limit.py`) — checa só
  `Content-Length`, sem bufferizar o corpo inteiro; não protege contra corpo chunked sem esse
  header, mas o único cliente real (nó `HTTP Request` do n8n) sempre o envia pra um corpo JSON.

**Não resolvido, fora do escopo desta correção** (mesmo residual de sempre, não revalidado):
credencial `telegramApi` nunca configurada nem testada contra a API real do Telegram — ver seção
acima.
