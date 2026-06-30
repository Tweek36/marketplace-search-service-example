FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .[migrations]

RUN addgroup --system --gid 1000 appuser && \
    adduser --system --uid 1000 --home /home/appuser --ingroup appuser appuser

USER appuser

COPY . .

EXPOSE 8003

CMD ["python", "-m", "bin.api"]
