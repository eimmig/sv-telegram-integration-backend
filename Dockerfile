# Multi-stage build: uv resolve/instala as dependencias travadas pelo uv.lock, runtime so leva
# o venv pronto + tesseract-ocr (binario chamado em runtime por pytesseract, nao so em build).
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# SonarCloud (docker:S8541) sinaliza esta linha por nao ter --no-build (protege contra sdist
# malicioso rodando setup.py arbitrario em dependencia de terceiro). --no-build nao da pra usar
# aqui de verdade: o pacote proprio nao tem wheel pre-pronto e teria que ser "buildado" de
# qualquer forma (uv_build, backend deste projeto - nao setup.py de terceiro, sem o risco que a
# regra mira). Tentativa de contornar construindo o wheel a parte e instalando-o depois
# (RUN uv build --wheel && uv pip install --no-deps --no-build dist/<nome-fixo>.whl) so trocou
# de achado: SonarCloud passou a reportar docker:S8544 ("using dependencies without locking
# resolved versions") no install de um caminho de arquivo local, pinado ou nao - a regra nao
# reconhece instalacao por path local como "resolvida", so instalacao por nome+versao de
# registry. Sem alternativa real dentro do proprio Dockerfile - achado marcado Won't Fix no
# SonarCloud com esta justificativa (ver evidence de feat-007 em feature_list.json deste
# repositorio).
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
