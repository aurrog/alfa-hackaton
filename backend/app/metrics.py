"""Метрики Prometheus (эндпоинт /metrics у API и отдельный порт у воркера)."""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("http_requests_total", "HTTP-запросы", ["method", "route", "status"])
HTTP_LATENCY = Histogram("http_request_duration_seconds", "Длительность HTTP-запросов", ["route"],
                         buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
JOBS = Counter("pipeline_jobs_total", "Задачи конвейера", ["kind", "result"])
JOB_LATENCY = Histogram("pipeline_job_duration_seconds", "Длительность задач конвейера", ["kind"])
INTEGRATION_CALLS = Counter("integration_calls_total", "Вызовы внешних источников", ["source", "status"])
INTEGRATION_LATENCY = Histogram("integration_call_duration_seconds", "Длительность вызовов внешних источников", ["source"])
TRANSITIONS = Counter("application_transitions_total", "Переходы статусов заявок", ["transition"])
DECISIONS = Counter("credit_decisions_total", "Кредитные решения", ["outcome", "level"])
