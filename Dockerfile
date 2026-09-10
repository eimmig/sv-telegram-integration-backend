# Multi-stage build: uv resolve/instala as dependencias travadas pelo uv.lock, runtime so leva
# o venv pronto + tesseract-ocr (binario chamado em runtime por pytesseract, nao so em build).
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# --no-build so nas dependencias de terceiros (risco de supply chain - sdist malicioso
# rodando setup.py arbitrario); o pacote proprio (fonte confiavel, mesmo repositorio) e
# instalado numa segunda passada, ja com as dependencias resolvidas.
RUN uv sync --frozen --no-dev --no-install-project --no-build
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN useradd --system --create-home app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "telegram_integration.main:app", "--host", "0.0.0.0", "--port", "8000"]
