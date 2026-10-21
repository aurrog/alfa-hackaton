# syntax=docker/dockerfile:1
# Образ бэкенда: API (uvicorn), воркер конвейера и миграции — одна сборка, разные команды
FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
# зависимости зафиксированы с хэшами: сборка воспроизводима и защищена от подмены пакетов
COPY requirements.lock .
RUN pip install --require-hashes --no-deps -r requirements.lock

COPY alembic.ini pyproject.toml ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

RUN useradd --system --uid 10001 --home /app app \
    && mkdir -p /data/uploads && chown -R app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=12 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
