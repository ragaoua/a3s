FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY src /app/src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

CMD ["/app/.venv/bin/a3s-agent"]
