"""Машина состояний, отказоустойчивый клиент источников, безопасность, контракт API (без БД)."""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain.state_machine import TRANSITIONS, Actor, TransitionError, available_transitions, reachable_statuses, resolve
from app.domain.statuses import STATUS_META, TERMINAL_STATUSES, AppStatus
from app.integrations import client as ic
from app.integrations.client import CircuitBreaker, IntegrationClient, IntegrationError, NotFoundInSource, Sources
from app.main import app
from app.security import create_token, decode_token, hash_password, verify_password


# ------------------------------------------------------------------ машина состояний
def test_every_status_has_metadata_and_is_reachable():
    assert set(STATUS_META) == set(AppStatus)
    assert reachable_statuses() == set(AppStatus)


def test_terminal_statuses_have_no_exits():
    for t in TRANSITIONS:
        assert not (t.sources & TERMINAL_STATUSES), t.name


def test_transition_names_unique():
    names = [t.name for t in TRANSITIONS]
    assert len(names) == len(set(names)) == 25


@pytest.mark.parametrize("name,frm,actor,to", [
    ("submit", "draft", Actor.CLIENT_SIGNER, AppStatus.SUBMITTED),
    ("submit", "pending_signature", Actor.CLIENT_SIGNER, AppStatus.SUBMITTED),
    ("send_for_signature", "draft", Actor.CLIENT, AppStatus.PENDING_SIGNATURE),
    ("auto_offer", "scoring", Actor.SYSTEM, AppStatus.OFFER_ISSUED),
    ("escalate", "manual_review", Actor.ANALYST, AppStatus.COMMITTEE_REVIEW),
    ("committee_offer", "committee_review", Actor.COMMITTEE, AppStatus.OFFER_ISSUED),
    ("disbursed", "disbursement", Actor.SYSTEM, AppStatus.ISSUED),
])
def test_allowed_transitions(name, frm, actor, to):
    assert resolve(name, frm, actor).target == to


def test_signer_can_do_what_client_can():
    assert resolve("send_for_signature", "draft", Actor.CLIENT_SIGNER).target == AppStatus.PENDING_SIGNATURE


@pytest.mark.parametrize("name,frm,actor,code", [
    ("submit", "draft", Actor.CLIENT, "forbidden_transition"),  # нет права подписи
    ("analyst_offer", "committee_review", Actor.ANALYST, "invalid_transition"),
    ("committee_offer", "committee_review", Actor.ANALYST, "forbidden_transition"),
    ("accept_offer", "issued", Actor.CLIENT_SIGNER, "invalid_transition"),
    ("teleport", "draft", Actor.SYSTEM, "unknown_transition"),
])
def test_forbidden_transitions(name, frm, actor, code):
    with pytest.raises(TransitionError) as e:
        resolve(name, frm, actor)
    assert e.value.code == code


def test_available_transitions_for_analyst():
    names = {t.name for t in available_transitions("manual_review", Actor.ANALYST)}
    assert names == {"analyst_offer", "analyst_decline", "analyst_request_info", "escalate", "rerun"}


def test_bank_statuses_have_sla():
    assert STATUS_META[AppStatus.MANUAL_REVIEW].sla_hours and STATUS_META[AppStatus.COMMITTEE_REVIEW].sla_hours


# ------------------------------------------------------------------ предохранитель и повторы
def test_circuit_breaker_opens_and_half_opens():
    br = CircuitBreaker(threshold=2, reset_sec=0.05)
    assert br.allow()
    br.failure()
    assert br.allow() and br.state == "closed"
    br.failure()
    assert not br.allow() and br.state == "open"
    time.sleep(0.06)
    assert br.allow() and br.state == "half_open"
    br.success()
    assert br.state == "closed"


@pytest.fixture
def transport():
    calls = {"n": 0}
    script: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        step = script[min(calls["n"] - 1, len(script) - 1)]
        if isinstance(step, Exception):
            raise step
        return httpx.Response(step[0], json=step[1])

    client = httpx.Client(base_url="http://mocks", transport=httpx.MockTransport(handler))
    ic.set_http_client(client)
    ic.reset_breakers()
    yield script, calls
    ic.set_http_client(None)
    ic.reset_breakers()


def test_retry_then_success(transport, monkeypatch):
    monkeypatch.setattr(ic.time, "sleep", lambda s: None)
    script, calls = transport
    script += [(503, {"error": "down"}), (200, {"inn": "1"})]
    assert Sources(IntegrationClient(retries=2)).egrul("1") == {"inn": "1"}
    assert calls["n"] == 2


def test_not_found_is_not_retried(transport):
    script, calls = transport
    script.append((404, {"error": "not_found"}))
    with pytest.raises(NotFoundInSource):
        Sources(IntegrationClient(retries=2)).egrul("1")
    assert calls["n"] == 1


def test_client_error_is_not_retried(transport):
    script, calls = transport
    script.append((422, {"error": "consent_required"}))
    with pytest.raises(IntegrationError) as e:
        Sources(IntegrationClient(retries=2)).bki("bki_company", {"inn": "1"}, {})
    assert e.value.kind == "rejected" and not e.value.retryable and calls["n"] == 1


def test_timeouts_exhaust_retries_and_open_breaker(transport, monkeypatch):
    monkeypatch.setattr(ic.time, "sleep", lambda s: None)
    script, calls = transport
    script.append(httpx.ReadTimeout("slow"))
    src = Sources(IntegrationClient(retries=1))
    for _ in range(5):
        with pytest.raises(IntegrationError):
            src.fns("1")
    with pytest.raises(IntegrationError) as e:
        src.fns("1")
    assert e.value.kind == "circuit_open"
    assert calls["n"] == 10  # 5 вызовов × 2 попытки, шестой отсечён предохранителем


def test_abs_client_absent_returns_none(transport):
    script, _ = transport
    script.append((404, {"error": "not_a_client"}))
    assert Sources(IntegrationClient(retries=0)).abs_client("1") is None


# ------------------------------------------------------------------ безопасность
def test_password_hashing():
    h = hash_password("Demo-2026")
    assert h.startswith("$argon2id$") and verify_password("Demo-2026", h)
    assert not verify_password("demo-2026", h) and not verify_password("x", "not-a-hash")


def test_jwt_roundtrip():
    import uuid
    uid = uuid.uuid4()
    token, exp = create_token(uid, "bank", "analyst")
    payload = decode_token(token)
    assert payload["sub"] == str(uid) and payload["role"] == "analyst" and payload["kind"] == "bank"


# ------------------------------------------------------------------ контракт API
@pytest.fixture(scope="module")
def api():
    return TestClient(app)


def test_openapi_has_key_paths(api):
    spec = api.get("/api/openapi.json").json()
    paths = spec["paths"]
    for p in ["/api/v1/auth/login", "/api/v1/applications", "/api/v1/applications/{app_id}/submit",
              "/api/v1/bank/queue", "/api/v1/bank/applications/{app_id}/decision", "/api/v1/bank/policy",
              "/api/v1/feed", "/api/v1/meta/state-machine"]:
        assert p in paths, p
    assert spec["info"]["version"] == "1.0.0"


def test_live_and_request_id(api):
    r = api.get("/api/health/live", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 200 and r.headers["X-Request-ID"] == "abc123"


def test_meta_endpoints(api):
    sm = api.get("/api/v1/meta/state-machine").json()
    assert len(sm["statuses"]) == 17 and len(sm["transitions"]) == 25 and len(sm["client_stages"]) == 6
    d = api.get("/api/v1/meta/dictionaries").json()
    assert d["scorecard"]["features"] and d["decline_reasons"]


def test_validation_error_is_problem_json(api):
    r = api.post("/api/v1/auth/login", json={"email": "x"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "validation_failed" and body["errors"] and body["request_id"]


def test_protected_endpoint_requires_token(api):
    r = api.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    r = api.get("/api/v1/auth/me", headers={"Authorization": "Bearer broken"})
    assert r.status_code == 401 and r.json()["code"] == "invalid_token"


# ------------------------------------------------------------------ LLM с открытыми весами (необязательно)
def test_llm_disabled_by_default_and_fallback(monkeypatch):
    from app.config import get_settings
    from app.services import llm

    assert llm.chat("system", "user") is None  # LLM_PROVIDER=none
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "openai_compatible")
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, model=json["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": " Ответ модели "}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.chat("system", "user") == "Ответ модели"
    assert sent["url"].endswith("/chat/completions") and sent["model"] == s.llm_model

    def broken(url, json, timeout):
        raise httpx.ConnectError("ollama is down")

    monkeypatch.setattr(llm.httpx, "post", broken)
    assert llm.chat("system", "user") is None  # недоступность модели не ломает сценарий


def test_memo_is_built_from_dossier_numbers():
    from app.services.memo import build_memo

    d = {"application": {"number": "КЗ-1", "product": {"name": "Экспресс"}, "amount": 1_500_000, "term_months": 24,
                         "purpose": "equipment", "purpose_text": None, "manual_reasons": ["Сумма выше лимита"]},
         "company": {"name": "ИП Тест", "inn": "165573184679", "ogrn": "1", "registration_date": "2020-01-01",
                     "okved_code": "56.10", "okved_name": "Рестораны", "msp_category": "micro", "is_bank_client": True,
                     "bank_client_since": "2022-01-01"},
         "recommendation": {"outcome": "approve", "amount": 1_500_000, "term_months": 24, "rate": 21.5, "monthly_payment": 77447.36,
                            "conditions": ["Условие"], "level_title": "Аналитик", "policy_version": 1, "model_version": "1.0.0",
                            "affordability": {"sector_margin": 0.12, "operating_cash_flow": 162000, "min_dscr": 1.3,
                                              "max_new_payment": 103615, "binding_cap": "dscr", "dscr_at_offer": 1.64}},
         "scoring": {"model": "sme 1.0.0", "score": 688, "pd": 0.012, "grade": "A", "factors": []},
         "derived": {"monthly_revenue": 1_350_000, "revenue_source": "обороты в банке", "declared_monthly_revenue": 1_350_000,
                     "existing_monthly_payments": 21_000},
         "checks": [{"title": "Налоги", "details": "долг", "source": "ФНС", "result": "warn"}]}
    md = build_memo(d)
    assert md["provider"] == "template"
    text = md["markdown"]
    assert "1 500 000 ₽" in text and "PD 1,20%" in text and "DSCR при предлагаемых условиях: 1,64" in text and "под 21,5%" in text
    assert "Сумма выше лимита" in text and "Налоги: долг" in text
