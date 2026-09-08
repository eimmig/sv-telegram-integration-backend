# Log de Progresso — telegram-integration

## Estado Atual (Current State)

**Última atualização:** 2026-09-08
**Feature ativa:** nenhuma (`feat-001`/`feat-002` `done`; `feat-003` é a próxima elegível)

## Status

### O que está pronto

- [x] Harness deste serviço criado.
- [x] `feat-001` (Setup do projeto Python + webhook n8n) — `done` em 2026-09-08.

### Em andamento

- Nenhuma feature iniciada.

### Próximos passos (Next Steps)

1. `feat-002` (Parsing de mensagens não estruturadas) — única feature elegível agora.

## `feat-001` fechada — bootstrap uv + FastAPI + i18n + n8n (2026-09-08)

Primeiro serviço Python do backlog — nenhum código existia antes desta sessão. 3 subtasks
(SV-182..184, story SV-181), 3 PRs de subtask (#1, #2, #3) + 1 PR de story (#4, `feature ->
develop`), todos com CI real e verde (execução de verdade — `uv sync`/`ruff`/`mypy`/`pytest --cov`
rodando no runner, não guarda pulada).

**Bootstrap real, não escrito à mão**: `pyproject.toml`/`uv.lock` gerados via `uv init`/`uv add`
de verdade (versões resolvidas do PyPI, mesmo padrão de `start.spring.io` usado em
`api-gateway feat-001`). **FastAPI + Uvicorn** decidido como framework HTTP (nenhuma nota fixava
isso antes) — registrado em `docs/CONVENTIONS.md` (repositório raiz `sv-harness`). `GET /health`
prova o app de pé. i18n (`locales/{pt-BR,en-US,es}.json` + `resolve_locale`/`get_message`, uma
chave real `generic_error`) prova o mecanismo ponta a ponta, mesmo padrão já aceito em
`auth-service feat-001.5`/`api-gateway feat-001.3`. `n8n/telegram-bot.json` (Telegram Trigger +
normalização) exportado parando propositalmente antes do nó `HTTP Request` — a chamada real
n8n → Python fica para `feat-002`, quando o endpoint de parsing existir; risco residual
documentado em `n8n/README.md` (JSON não validado contra instância real de n8n —
`docs.n8n.io/workflows/export-import` retornou 404 durante a pesquisa, grounding via fonte
secundária).

**Impedimento real resolvido antes de codificar**: `uv` não estava instalado nesta máquina —
`Scripts` global do Python é somente leitura sem admin, corrigido via `pip install --user uv` +
cópia do executável para `~/.local/bin` (já no PATH desta sessão, mesmo mecanismo do gotcha
anterior do `claude.exe`) + PATH do usuário persistido via PowerShell para sessões futuras.

**2 achados reais de sequenciamento de CI, corrigidos rodando os PRs de verdade** (mesma
armadilha já documentada em `docs/CI-CD.md` para os outros 6 repositórios, nunca portada para
este até agora): passo de i18n guardado só por `pyproject.toml` quebraria a subtask de bootstrap
antes de `locales/` existir — corrigido para guarda própria por `locales/pt-BR.json`; passo de
changelog rodando em todo PR (não só `story -> develop`) quebrou de verdade a PR da subtask 2
(`CHANGELOG.md` já populado inteiro desde a criação da story via `jira_story.py`, sem diff novo
por subtask) — corrigido para guarda por `base_ref`.

**Achado real de documentação corrigido**: `docs/OBSERVABILITY-AND-CONFIG.md` dizia que o
`/health` deste serviço verifica conectividade com "RabbitMQ/n8n" — nenhuma nota sustentava isso
(o serviço nunca fala com RabbitMQ nem chama n8n, é o contrário). Corrigido na própria nota.

**Delivery Reviewer** (passe próprio): PASS, 1 achado real corrigido antes de fechar —
`resolve_locale` usava `startswith` (um `language_code` de 1 caractere como `"e"` casava por
acidente com `en-US`) — corrigido para comparação exata do subtag de idioma (parte antes do
`-`). **Test Suite Auditor**: PASS — testes provam mapeamento de locale real (parametrizado,
casos de fallback), nenhum teste trivial.

**Achado real do SonarCloud** (PR story → develop, primeira análise de verdade deste
repositório): Security Rating E em "Avoid binding the application to all network interfaces" —
o entrypoint de dev `main()` usava `host="0.0.0.0"`; corrigido para `"127.0.0.1"` (bind em todas
as interfaces só faz sentido num deploy real via Dockerfile/container, decisão de infra futura,
não deste script de conveniência local).

12 testes, 0 falhas, cobertura 100% (gate 80%). `./init.sh` do serviço e da raiz verdes. Libera
`feat-002` (parsing de mensagens); `epic-005` (raiz) continua `in-progress` até `feat-002..005`
também fecharem.

## `feat-002` fechada — OCR + extração heurística + fallback conversacional (2026-09-08)

Impedimento real resolvido antes de codificar: `feat-002` ("Parsing de mensagens não
estruturadas") nunca teve o formato da mensagem definido em nenhuma nota. Decisão tomada com o
usuário (`AskUserQuestion`, 2 perguntas, registrada em `docs/DECISIONS-LOG.md`): usuário pode
enviar **foto do bilhete** (a casa de apostas gera esse comprovante nativamente) **ou texto
livre**; motor de OCR = **Tesseract local** via `pytesseract`, não API de nuvem (sem custo, sem
segredo, sem dependência de rede externa — alinhado ao resto do projeto). Sem amostra real de
bilhete disponível (usuário: "as diferentes casas têm diferentes modelos... teria que tentar
buscar as infos meio genericamente"), então a extração é heurística genérica, sem template por
casa, com fallback conversacional explicitamente autorizado pelo usuário ("caso ache isso demais,
pode usar o modelo do cadastro bot pergunta e tu responde").

**Ambiente**: Tesseract não estava instalado nesta máquina — `choco` falhou por falta de admin,
resolvido via `winget` (já estava instalado, só fora do PATH) + `tessdata` `por`/`eng` baixados
pra `~/.local/tessdata` (Program Files é read-only sem admin) + `TESSDATA_PREFIX`/`TESSERACT_CMD`
persistidos via PowerShell.

**Módulos novos**: `conversation.py` (estado de conversa no Redis já provisionado em `infra/`
para `stats-service`, TTL 15min, testado com `testcontainers.community.redis` real — não
`fakeredis`, mesmo padrão Testcontainers já usado nos 3 serviços Java). `ocr.py`
(`pytesseract`, `por+eng`, nunca lança exceção — bytes inválidos viram `""`, testado com imagem
sintética renderizada via Pillow, já que não há bilhete real disponível). `extraction.py` (só
`odd`/`stake`/`bet_date` — padrão léxico universal, número decimal/prefixo de moeda/data — e
`betting_house` — lista curta de casas brasileiras conhecidas — são extraídos com confiança real;
`sport`/`league`/`market`/`team1`/`team2` **sempre `None`**, documentado como não tentado em vez
de fingir robustez que não existe; `parse_direct_answer` normaliza resposta direta a uma pergunta
específica, mais permissivo que a busca em texto livre). `orchestration.py` (funde extração nova
com estado pendente, pergunta o primeiro campo obrigatório faltante ou retorna resultado
completo). `main.py` (`POST /bets/capture` — Pydantic, texto ou foto base64, roda OCR se foto).

**2 achados reais MAJOR do Plan Review, corrigidos antes de codificar**: (1) `bets-service`
espera IDs de catálogo (`bettingHouseId`/`sportId`/`leagueId`/`marketId` — UUID), não nomes — OCR
só produz nomes; escopo desta feature reduzido pra produzir campos **brutos**, resolução
nome→catálogo fica pra `feat-004`, não empurrada indevidamente pra cá. (2) plano original cogitava
o próprio Python baixar a foto via Telegram Bot API (`getFile`), exigindo `TELEGRAM_BOT_TOKEN`
como segredo novo neste serviço — corrigido pra n8n baixar (já tem a credencial do Telegram
configurada no Trigger desde `feat-001`) e passar a imagem em base64 — Python nunca vê o token do
bot, mantendo n8n como único dono de credencial do Telegram.

**2 achados reais encontrados durante a implementação/revisão** (não no Plan Review): caminho de
resposta direta a uma pergunta armazenava texto cru sem normalizar (data "08/09/2026" em vez de
"2026-09-08", inconsistente com o caminho de extração de mensagem única) — corrigido com
`parse_direct_answer`. Delivery Reviewer encontrou dict de campos **esparso** no fluxo
multi-turno (só as chaves que tiveram valor real, formato inconsistente com o de 9 chaves da
extração de mensagem única) — corrigido em `_merge`; só foi pego depois de escrever um teste novo
ponta a ponta pela HTTP real (`test_multi_turn_conversation_carries_state_across_separate_requests`)
— os testes de `orchestration.py` sozinhos, chamando `handle_message` direto, não expunham o bug.

`n8n/telegram-bot.json` estendido: nó `IF` ramifica foto/texto, nó `Telegram` baixa a foto (maior
resolução, `resource: file`/`operation: get`), nó `HTTP Request` chama o endpoint novo, nó
`Telegram` `sendMessage` responde ao usuário. Residual risk expandido em `n8n/README.md` (4
pontos não validados contra instância real, ordenados por risco — expressão de binário→base64 é
o mais incerto).

4 subtasks (SV-186..189, story SV-185), 4 PRs de subtask (#5, #6, #7, #8) + 1 PR de story (#9,
`feature -> develop`), todos com CI real e verde — Tesseract instalado no runner (achado real: só
o wrapper `pip` estava sendo instalado antes, não o motor de OCR em si) e Redis via
`testcontainers` rodando de verdade no CI, não só localmente. SonarCloud verde de primeira. 45
testes, 0 falhas, cobertura 100% (gate 80%). `./init.sh` do serviço e da raiz verdes.

## `feat-002.5` — extração validada contra 5 bilhetes reais (2026-09-08, reabertura no mesmo dia)

Usuário forneceu 5 capturas reais de bilhetes de casas de apostas brasileiras (Bet365 e mais 4,
não commitadas no repo — dados de aposta/financeiro, mantidas só na máquina local). Rodei OCR de
verdade (`pytesseract`, não só leitura visual) + `extract_fields` contra as 5 — 2 achados reais
confirmados e corrigidos:

1. **Odd podia capturar um valor de moeda em vez da odd real** — "Valor Total R$2.50" (stake)
   vencia a odd real "5.50" por aparecer antes no texto (o bare-scan de odd não excluía números
   prefixados por R$/$). Corrigido excluindo valores de moeda do escaneio de odd antes de buscar.
2. **`bet_date` era extraído de qualquer padrão dd/mm/aaaa no texto, mas o bilhete normalmente
   mostra a data do EVENTO, não da aposta** (2 dos 5 bilhetes reais confirmam isso — ex.:
   "Dortmund x Villarreal 08/09/26" é a data do jogo). Dado errado silencioso é pior que campo
   ausente — removido por completo; `orchestration.py` agora sempre usa a data de hoje (servidor)
   quando `bet_date` não vem de outra fonte, e o campo saiu de `REQUIRED_FIELDS` (nunca mais
   perguntado ao usuário).

Testado também `--psm 6` do Tesseract como alternativa — resolveria o reordenamento de layout em
coluna e a perda do ponto decimal em 2 dos 5 bilhetes, mas piorou silenciosamente o stake de
outro bilhete (R$2,50 virou "R$250" sem separador — erro de 100x no valor). Risco assimétrico
(dado errado silencioso é pior que uma pergunta extra) — mantido o `psm` padrão, documentado como
limitação aceita em vez de perseguida com mais regex.

Resultado final contra as 5 amostras reais, ponta a ponta (OCR + extração): **stake correto 5/5**,
**odd correto 2/5** (Bet365 e um bilhete genérico) com os outros 3/5 (Betano, Novibet, Vupi)
caindo com segurança no fallback conversacional em vez de capturar um valor errado — a odd em
texto colorido/riscado (boost) do Betano vira lixo na OCR, o Novibet perde o símbolo `@` e o
ponto decimal, o Vupi tem layout em coluna que a OCR reordena e também perde o decimal
especificamente no valor da odd (os valores em R$ do mesmo bilhete saíram corretos). Isso não é
regressão — é o design já combinado com o usuário (heurística genérica + pergunta quando incerto)
funcionando como esperado diante de casos genuinamente difíceis.

Delivery Reviewer: PASS — 1 achado residual menor: `bet_date` usa data UTC, não horário de
Brasília (possível off-by-one perto da meia-noite BRT) — aceito, nenhuma convenção de timezone
existe no projeto pra violar. 1 subtask (SV-190), 1 PR de subtask (#10) + 1 PR de story (#11,
`feature -> develop`), CI + SonarCloud verdes. 45 testes, 0 falhas, cobertura 100%.

## Bloqueios / Riscos

- Nenhum aberto. `n8n/telegram-bot.json` tem 4 pontos não validados contra instância real,
  documentados em `n8n/README.md` — não bloqueante, revisitar antes de produção.
- `POST /bets/capture` sem autenticação própria nem limite de tamanho de corpo pro base64 da
  foto — aceitável no estágio atual (rede local/interna, serviço não containerizado/exposto),
  revisitar quando containerizado.

## Harness criado (2026-07-30)

`CLAUDE.md`, `feature_list.json`, `init.sh`, `progress.md`, `session-handoff.md` criados — sem
código de aplicação ainda. Ver `../../docs/services/telegram-integration.md` para o fluxo
completo.
