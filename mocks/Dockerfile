# syntax=docker/dockerfile:1
# Симулятор внешних систем (ЕГРЮЛ/ЕГРИП, ФНС, реестр МСП, стоп-листы, БКИ, АБС)
FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes --no-deps -r requirements.lock
COPY simulator ./simulator
RUN useradd --system --uid 10002 mocks
USER mocks
EXPOSE 8081
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=2).status == 200 else 1)"
CMD ["uvicorn", "simulator.main:app", "--host", "0.0.0.0", "--port", "8081", "--log-level", "warning", "--no-server-header"]
