FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_DEV=1 \
    UV_FROZEN=1 \
    PYTHONPATH=/app \
    PATH="/home/appuser/.local/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN /root/.local/bin/uv sync --frozen --no-install-project --no-dev

RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --home /home/appuser --ingroup appuser appuser && \
    mkdir -p /home/appuser/.local/bin && \
    cp /root/.local/bin/uv /home/appuser/.local/bin/ && \
    chown -R appuser:appuser /app /home/appuser/.local

USER appuser

COPY . .

EXPOSE 8003

CMD ["/home/appuser/.local/bin/uv", "run", "python", "-m", "bin.api"]
