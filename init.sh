#!/usr/bin/env bash
# Verification for telegram-integration (Python 3.12+).
set -euo pipefail

# Windows' official python.org installer only ships 'python.exe', not 'python3' — try
# both, in that order. A fake Microsoft Store stub can also resolve on PATH but only
# print a redirect message instead of a version; skip it and try the next candidate.
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    version="$("$candidate" --version 2>&1 | head -n1 || true)"
    if [[ "$version" =~ [0-9] ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "MISS no real Python 3.12+ found on PATH (tried python3, python)"
  exit 1
fi
echo "OK   $version — resolved as '$PYTHON'"

if [ -f "requirements.txt" ] && [ ! -f "pyproject.toml" ]; then
  echo "FAIL requirements.txt found without pyproject.toml, but docs/CONVENTIONS.md decided"
  echo "     uv (pyproject.toml) as the dependency manager for this service. Migrate, or get"
  echo "     docs/CONVENTIONS.md updated first if this needs to change."
  exit 1
fi

if [ -f "pyproject.toml" ]; then
  echo "OK   Python project detected (pyproject.toml)"
  if ! command -v uv >/dev/null 2>&1; then
    echo "MISS uv not found on PATH (see docs/CONVENTIONS.md)"
    exit 1
  fi
  uv sync
  echo "..   ruff check"
  uv run ruff check .
  echo "..   mypy"
  uv run mypy .
  echo "..   pytest (with coverage)"
  uv run pytest --cov --cov-fail-under=80
else
  echo "----  No pyproject.toml yet — feat-001 not started."
  echo "     See feature_list.json for the next step."
  exit 1
fi

echo "telegram-integration verification passed."
