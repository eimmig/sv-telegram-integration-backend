# Session Handoff — telegram-integration

> Estado atual, não histórico. O diário cronológico é o `progress.md` — este arquivo é reescrito
> a cada sessão para responder "o que a próxima sessão precisa saber agora".

**Última atualização:** 2026-11-04

## Objetivo atual

`feat-001`..`feat-015` `done`. `feat-016` (odd/stake vazia chega ao envio e gera `400`) `not-started`.

## Concluído nesta sessão (2026-11-04)

- [x] **`feat-014` fechada** (`epic-049`): sem vínculo, catálogo e envio respondem
      `bet_submit_no_link` pelo `type` do `404` do gateway; `401` virou indisponibilidade com log de
      erro. Story SV-806, PRs #62..#65.

## Bloqueios / Riscos

- `develop` à frente de `main`: falta a release `develop -> main` e o `kubectl rollout restart` do
  telegram-integration (o deploy automático do CI não alcança a rede local).
- Usuário sem vínculo só recebe a orientação depois de responder odd/stake (fora do escopo de
  `feat-014`; virar feature só se o usuário pedir).

## Próxima sessão — por onde começar

1. Rodar `./init.sh` (Docker Desktop aberto: os testes usam Testcontainers).
2. `feat-016`.
