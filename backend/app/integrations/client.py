"""Отказоустойчивый клиент внешних источников.

* Таймауты на подключение и чтение.
* Повторы с экспоненциальной паузой и джиттером только для временных ошибок
  (таймаут, 5xx, обрыв соединения); 4xx не повторяются.
* Предохранитель (circuit breaker) на каждый источник: после N ошибок подряд
  источник временно «размыкается», и конвейер не тратит время на заведомо
  неуспешные вызовы, а сразу уходит в деградированный режим.
* Каждый вызов журналируется в integration_calls (запрос, ответ, длительность,
  номер попытки, request_id) — это аудит и «происхождение данных» для аналитика.
"""

from __future__ import annotations

import json
import random
import threading
import time
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_setup import request_id_var
from app.metrics import INTEGRATION_CALLS, INTEGRATION_LATENCY
from app.models import IntegrationCall

SOURCE_TITLES = {
    "egrul": "ЕГРЮЛ/ЕГРИП",
    "fns": "ФНС «Прозрачный бизнес»",
    "msp": "Единый реестр субъектов МСП",
    "aml": "Перечни и стоп-листы",
    "bki_company": "БКИ — компания",
    "bki_owner": "БКИ — собственник",
    "abs_client": "АБС банка — обороты клиента",
    "abs_disburse": "АБС банка — выдача кредита",
}


class IntegrationError(Exception):
    def __init__(self, source: str, kind: str, message: str, retryable: bool = True, http_status: int | None = None):
        super().__init__(f"{source}: {kind}: {message}")
        self.source = source
        self.kind = kind
        self.retryable = retryable
        self.http_status = http_status


class NotFoundInSource(IntegrationError):
    def __init__(self, source: str, message: str = "not found"):
        super().__init__(source, "not_found", message, retryable=False, http_status=404)


@dataclass
class CircuitBreaker:
    threshold: int
    reset_sec: float
    failures: int = 0
    opened_at: float | None = None

    def __post_init__(self):
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.opened_at is None:
                return True
            # полуоткрыт по истечении паузы: пропускаем пробный вызов
            return time.monotonic() - self.opened_at >= self.reset_sec

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if time.monotonic() - self.opened_at >= self.reset_sec else "open"


_breakers: dict[str, CircuitBreaker] = {}
_http: httpx.Client | None = None
_lock = threading.Lock()


def breaker(source: str) -> CircuitBreaker:
    with _lock:
        if source not in _breakers:
            s = get_settings()
            _breakers[source] = CircuitBreaker(s.circuit_breaker_threshold, s.circuit_breaker_reset_sec)
        return _breakers[source]


def breaker_states() -> dict[str, str]:
    return {k: v.state for k, v in _breakers.items()}


def reset_breakers() -> None:
    with _lock:
        _breakers.clear()


def http_client() -> httpx.Client:
    global _http
    if _http is None:
        s = get_settings()
        _http = httpx.Client(base_url=s.integrations_base_url,
                             timeout=httpx.Timeout(s.integration_timeout_sec, connect=2.0))
    return _http


def set_http_client(client: httpx.Client | None) -> None:
    """Подменить HTTP-клиент (тесты: in-process приложение моков; наполнение: без задержек)."""
    global _http
    _http = client


def _short(d: dict | None, limit: int = 20000) -> dict | None:
    if d is None:
        return None
    raw = json.dumps(d, ensure_ascii=False, default=str)
    return d if len(raw) <= limit else {"truncated": True, "size": len(raw)}


class IntegrationClient:
    def __init__(self, session: Session | None = None, application_id: uuid.UUID | None = None,
                 retries: int | None = None):
        s = get_settings()
        self.session = session
        self.application_id = application_id
        self.retries = s.integration_retries if retries is None else retries

    def _record(self, source: str, status: str, attempt: int, ms: int, req: dict | None, resp: dict | None,
                error: str | None, http_status: int | None) -> None:
        INTEGRATION_CALLS.labels(source, status).inc()
        INTEGRATION_LATENCY.labels(source).observe(ms / 1000)
        if self.session is not None:
            self.session.add(IntegrationCall(
                application_id=self.application_id, source=source, status=status, attempt=attempt,
                duration_ms=ms, request=_short(req), response=_short(resp), error=error,
                http_status=http_status, request_id=request_id_var.get(),
            ))

    def call(self, source: str, method: str, path: str, json: dict | None = None,
             headers: dict | None = None) -> dict:
        br = breaker(source)
        req_log = {"method": method, "path": path, "body": json}
        if not br.allow():
            self._record(source, "circuit_open", 0, 0, req_log, None, "circuit breaker open", None)
            raise IntegrationError(source, "circuit_open", "источник временно отключён предохранителем")
        h = {"X-Request-ID": request_id_var.get() or uuid.uuid4().hex}
        if headers:
            h.update(headers)
        last: IntegrationError | None = None
        for attempt in range(1, self.retries + 2):
            t0 = time.perf_counter()
            try:
                r = http_client().request(method, path, json=json, headers=h)
                ms = int((time.perf_counter() - t0) * 1000)
                if r.status_code == 404:
                    self._record(source, "not_found", attempt, ms, req_log, _safe_json(r), None, 404)
                    br.success()
                    raise NotFoundInSource(source)
                if 400 <= r.status_code < 500:
                    self._record(source, "rejected", attempt, ms, req_log, _safe_json(r), r.text[:500], r.status_code)
                    br.success()
                    raise IntegrationError(source, "rejected", r.text[:300], retryable=False, http_status=r.status_code)
                if r.status_code >= 500:
                    self._record(source, "error", attempt, ms, req_log, _safe_json(r), r.text[:500], r.status_code)
                    last = IntegrationError(source, "http_error", f"HTTP {r.status_code}", http_status=r.status_code)
                else:
                    data = r.json()
                    self._record(source, "ok", attempt, ms, req_log, data, None, r.status_code)
                    br.success()
                    return data
            except (httpx.TimeoutException, httpx.TransportError) as e:
                ms = int((time.perf_counter() - t0) * 1000)
                kind = "timeout" if isinstance(e, httpx.TimeoutException) else "transport"
                self._record(source, "timeout" if kind == "timeout" else "error", attempt, ms, req_log, None, str(e), None)
                last = IntegrationError(source, kind, str(e) or kind)
            if attempt <= self.retries:
                time.sleep(min(0.2 * 2 ** (attempt - 1), 2.0) + random.uniform(0, 0.1))
        br.failure()
        assert last is not None
        raise last


def _safe_json(r: httpx.Response) -> dict | None:
    try:
        v = r.json()
        return v if isinstance(v, dict) else {"data": v}
    except ValueError:
        return {"text": r.text[:500]}


class Sources:
    """Типизированные обёртки над внешними сервисами (контракты упрощены, смысл сохранён)."""

    def __init__(self, client: IntegrationClient):
        self.c = client

    def egrul(self, inn: str) -> dict:
        return self.c.call("egrul", "GET", f"/egrul/v1/entities/{inn}")

    def fns(self, inn: str) -> dict:
        return self.c.call("fns", "GET", f"/fns/v1/transparent-business/{inn}")

    def msp(self, inn: str) -> dict:
        return self.c.call("msp", "GET", f"/msp-registry/v1/{inn}")

    def aml(self, inn: str, persons: list[dict]) -> dict:
        return self.c.call("aml", "POST", "/aml/v1/screening", json={"inn": inn, "persons": persons})

    def bki(self, source: str, subject: dict, consent: dict) -> dict:
        return self.c.call(source, "POST", "/bki/v1/credit-reports", json={"subject": subject, "consent": consent})

    def abs_client(self, inn: str) -> dict | None:
        try:
            return self.c.call("abs_client", "GET", f"/abs/v1/clients/{inn}")
        except NotFoundInSource:
            return None

    def abs_disburse(self, payload: dict, idempotency_key: str) -> dict:
        return self.c.call("abs_disburse", "POST", "/abs/v1/loans", json=payload,
                           headers={"Idempotency-Key": idempotency_key})
