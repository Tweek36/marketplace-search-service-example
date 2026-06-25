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

# Отладочная информация
RUN echo "=== Информация о пользователе и окружении ===" && \
    whoami && \
    echo "PATH: $PATH" && \
    which uv && \
    uv --version

COPY pyproject.toml uv.lock ./
# Устанавливаем все зависимости включая production
RUN echo "=== Установка всех зависимостей ===" && \
    uv sync --frozen --no-install-project && \
    echo "=== Список установленных пакетов ===" && \
    uv pip list

COPY . .

# Устанавливаем только production зависимости (без dev)
RUN echo "=== Установка production зависимостей ===" && \
    uv sync --frozen --no-install-project --no-dev && \
    echo "=== Список установленных production пакетов ===" && \
    uv pip list && \
    echo "=== Проверка наличия uvicorn ===" && \
    python -c "import uvicorn; print(f'uvicorn найден: {uvicorn.__version__}')" || echo "uvicorn НЕ найден"

EXPOSE 8003

CMD ["uv", "run", "python", "-m", "bin.api"]