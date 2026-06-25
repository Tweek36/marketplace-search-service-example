FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_DEV=1 \
    UV_FROZEN=1 \
    PYTHONPATH=/app \
    PATH="/home/appuser/.local/bin:$PATH"

# Устанавливаем зависимости и создаем пользователя
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя и его домашнюю директорию
RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --home /home/appuser --ingroup appuser --disabled-password --gecos "" appuser && \
    mkdir -p /home/appuser/.local/bin /app && \
    chown -R appuser:appuser /home/appuser /app

USER appuser
WORKDIR /app

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .

RUN uv sync --frozen --no-dev

EXPOSE 8003

CMD ["uv", "run", "python", "-m", "bin.api"]