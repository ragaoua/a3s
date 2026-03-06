FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY agent.py /app/agent.py

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/agent.py /app/agent.py

CMD ["sh", "-c", "/app/.venv/bin/uvicorn agent:a2a_app --host 0.0.0.0 --port ${LISTEN_PORT}"]
