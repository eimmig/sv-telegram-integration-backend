# Session Handoff — telegram-integration

> Estado atual, não histórico. O diário cronológico é o `progress.md` — este arquivo é reescrito
> a cada sessão para responder "o que a próxima sessão precisa saber agora".

**Última atualização:** 2026-11-02

## Objetivo atual

`feat-001`..`feat-013` e `feat-015` `done`. `feat-014` (sem vínculo recebe erro genérico) e
`feat-016` (odd/stake vazia chega ao envio e gera `400`) `not-started`.

## Concluído nesta sessão (2026-11-02)

- [x] **`feat-015` fechada**: comando `/cancelar` (alias `/cancel`) no serviço Python apaga a
      conversa pendente; foto nova reinicia a conversa; `4xx` permanente limpa o estado;
      `generic_error_pending` cita o comando. Fluxo n8n inalterado. Story SV-783, PRs #56..#60.
- [x] `feat-016` registrada no backlog (causa do `400` de produção).

## Bloqueios / Riscos

- Produção ainda roda a imagem antiga até um `kubectl rollout restart` manual do
  telegram-integration (o deploy automático do CI não alcança a rede local).
- Usuário sem vínculo continua vendo erro genérico (`feat-014`).

## Próxima sessão — por onde começar

1. Rodar `./init.sh` (deve passar).
2. `feat-016` (depende só do que já está no `develop`) ou `feat-014`.
