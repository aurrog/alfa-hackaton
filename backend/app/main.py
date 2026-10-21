"""Приложение FastAPI: `uvicorn app.main:app`."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import ROUTERS
from app.config import get_settings
from app.errors import install as install_errors
from app.logging_setup import log_extra, request_id_var, setup_logging, user_id_var
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS

log = logging.getLogger("app.http")

DESCRIPTION = """
API умного кредитного кабинета предпринимателя: кабинет клиента и рабочее место банка.

* **Аутентификация** — `POST /api/v1/auth/login` → `Authorization: Bearer <token>`. Тестовые учётки —
  `GET /api/v1/auth/demo-accounts`, пароль `Demo-2026`.
* **Ошибки** — RFC 7807 (`application/problem+json`) с полями `code`, `detail`, `request_id`.
* **Идемпотентность** — подпись заявки, принятие предложения и подпись договора принимают `Idempotency-Key`.
* **Конкурентность** — изменения заявки защищены оптимистической блокировкой (`version`), конфликт → `409`.
* **Трассировка** — `X-Request-ID` принимается и возвращается, попадает в журналы API, воркера и симулятора.
"""

TAGS = [
    {"name": "Аутентификация", "description": "Вход и профиль"},
    {"name": "Кабинет клиента", "description": "Подбор, заявка, подпись, предложение, договор, лента"},
    {"name": "Рабочее место банка", "description": "Очередь, досье, решения, политика, аудит"},
    {"name": "Справочники", "description": "Статусы, переходы, справочники"},
    {"name": "Служебные", "description": "Здоровье и метрики"},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    s.check_production_safety()
    log_extra(log, "api started", version=__version__, env=s.app_env)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    setup_logging(s.log_level)
    app = FastAPI(title="Умный кредитный кабинет — API", version=__version__, description=DESCRIPTION,
                  openapi_tags=TAGS, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json",
                  lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
                       expose_headers=["X-Request-ID", "Idempotent-Replayed"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id")
        if not rid or len(rid) > 64:
            rid = uuid.uuid4().hex
        token = request_id_var.set(rid)
        user_token = user_id_var.set(None)
        t0 = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            response.headers.setdefault("Cache-Control", "no-store")
            return response
        finally:
            dt = time.perf_counter() - t0
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_LATENCY.labels(path).observe(dt)
            if path not in ("/api/health/live", "/api/health/ready", "/metrics"):
                log_extra(log, "request", method=request.method, path=path, status=status, ms=round(dt * 1000, 1))
            request_id_var.reset(token)
            user_id_var.reset(user_token)

    install_errors(app)
    for r in ROUTERS:
        app.include_router(r)
    return app


app = create_app()
