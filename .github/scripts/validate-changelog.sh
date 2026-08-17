#!/usr/bin/env bash
# Falha o PR se o CHANGELOG.md do servico tocado nao foi atualizado no mesmo diff.
# Ver docs/CI-CD.md secao "Changelog por servico".
#
# Uso: validate-changelog.sh <caminho-do-changelog-relativo-a-raiz-do-repo>
# Espera BASE_SHA e HEAD_SHA no ambiente (setados pelo workflow a partir do evento pull_request).
set -euo pipefail

changelog_path="${1:?uso: validate-changelog.sh <caminho-do-CHANGELOG.md>}"

if [ -z "${BASE_SHA:-}" ] || [ -z "${HEAD_SHA:-}" ]; then
  echo "MISS BASE_SHA/HEAD_SHA nao definidos no ambiente - este passo so roda em pull_request."
  exit 1
fi

changed_files="$(git diff --name-only "$BASE_SHA" "$HEAD_SHA")"

if echo "$changed_files" | grep -qx "$changelog_path"; then
  echo "OK   $changelog_path foi atualizado neste PR."
  exit 0
fi

echo "FAIL $changelog_path nao foi atualizado neste PR."
echo "     Toda feature que altera este servico precisa de uma entrada em [Unreleased]"
echo "     (ver docs/CI-CD.md secao 'Changelog por servico')."
exit 1
