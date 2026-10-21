"""Сквозные бизнес-процессы на настоящей БД: клиентский путь, конвейер, рабочее место банка."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

pytestmark = pytest.mark.integration
PASSWORD = "Demo-2026"
PDF = b"%PDF-1.4\n% test\n%%EOF\n"


def create(c, product, amount, term, purpose="working_capital"):
    r = c.post("/api/v1/applications", json={"company_id": c.company["id"], "product_code": product, "amount": amount,
                                             "term_months": term, "purpose": purpose})
    assert r.status_code == 201, r.text
    return r.json()


def submit(c, app_id, key=None):
    return c.post(f"/api/v1/applications/{app_id}/submit", json={"password": PASSWORD, "consent_bki": True, "consent_pd": True},
                  headers={"Idempotency-Key": key or uuid.uuid4().hex})


def status(c, app_id):
    return c.get(f"/api/v1/applications/{app_id}").json()


def test_s1_express_auto_approval_to_disbursement(login, drain):
    anna = login("anna@kofe.test")
    comp = anna.get(f"/api/v1/companies/{anna.company['id']}").json()
    assert comp["preapproved"] and comp["preapproved"][0]["max_amount"] >= 1_500_000
    app = create(anna, "EXPRESS", 1_500_000, 24, "equipment")
    assert app["prefill"]["financials.monthly_revenue"]["source"].startswith("Обороты по счёту")
    assert submit(anna, app["id"]).status_code == 200
    drain()
    app = status(anna, app["id"])
    assert app["status"] == "offer_issued"
    assert (app["offer"]["amount"], app["offer"]["term_months"], app["offer"]["rate"]) == (1_500_000, 24, 21.5)
    assert anna.post(f"/api/v1/applications/{app['id']}/offer/accept").status_code == 200
    assert "Кредитный договор" in anna.get(f"/api/v1/applications/{app['id']}/contract").text
    assert anna.post(f"/api/v1/applications/{app['id']}/contract/sign", json={"password": PASSWORD}).status_code == 200
    drain()
    app = status(anna, app["id"])
    assert app["status"] == "issued" and app["loan"]["loan_account"].startswith("455")
    assert [s["state"] for s in app["stages"]] == ["done"] * 6
    assert anna.get("/api/v1/loans").json()["items"][0]["schedule"]


def test_idempotent_submit_and_wrong_password(login, drain):
    igor = login("igor@motor.test")
    app = create(igor, "EXPRESS", 1_000_000, 24)
    bad = igor.post(f"/api/v1/applications/{app['id']}/submit", json={"password": "wrong", "consent_bki": True, "consent_pd": True})
    assert bad.status_code == 422 and bad.json()["code"] == "bad_signature_password"
    no_consent = igor.post(f"/api/v1/applications/{app['id']}/submit", json={"password": PASSWORD, "consent_bki": False, "consent_pd": True})
    assert no_consent.json()["code"] == "consents_required"
    key = uuid.uuid4().hex
    first = submit(igor, app["id"], key)
    second = submit(igor, app["id"], key)
    assert first.status_code == second.status_code == 200
    assert second.headers.get("Idempotent-Replayed") == "true"
    assert len([s for s in status(igor, app["id"])["signatures"] if s["document_kind"] == "application"]) == 1
    reuse = igor.post(f"/api/v1/applications/{app['id']}/offer/accept", headers={"Idempotency-Key": key})
    assert reuse.status_code == 422 and reuse.json()["code"] == "idempotency_key_reused"
    drain()


def test_s3_counter_offer(login, drain):
    igor = login("igor@motor.test")
    app = create(igor, "EXPRESS", 3_000_000, 12, "equipment")
    submit(igor, app["id"])
    drain()
    app = status(igor, app["id"])
    assert app["status"] == "offer_issued" and app["offer"]["is_counter"]
    assert app["explanation"]["outcome"] == "counter_offer" and app["offer"]["changes"]


def test_s2_roles_authority_committee(login, drain):
    irina = login("irina@technostroy.test")
    app = create(irina, "INVEST", 40_000_000, 60, "equipment")
    irina.patch(f"/api/v1/applications/{app['id']}", json={"collateral": {"type": "real_estate", "value": 60_000_000}})
    for dt in ("financial_statements", "collateral_docs", "purchase_contract"):
        r = irina.post(f"/api/v1/applications/{app['id']}/documents", data={"doc_type": dt}, files={"file": (f"{dt}.pdf", PDF, "application/pdf")})
        assert r.status_code == 201, r.text
    r = submit(irina, app["id"])
    assert r.status_code == 403 and r.json()["code"] == "signer_required"
    assert irina.post(f"/api/v1/applications/{app['id']}/send-for-signature").json()["status"] == "pending_signature"
    oleg = login("oleg@technostroy.test")
    assert any("подписи" in n["title"] for n in oleg.get("/api/v1/notifications").json()["items"])
    assert submit(oleg, app["id"]).status_code == 200
    drain()
    analyst = login("analyst@bank.test")
    d = analyst.get(f"/api/v1/bank/applications/{app['id']}").json()
    assert d["application"]["status"] == "manual_review" and d["recommendation"]["outcome"] == "approve"
    assert any("Руководитель" in m for m in d["application"]["manual_reasons"])
    r = analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "approve", "version": d["application"]["version"]})
    assert r.status_code == 403 and r.json()["code"] == "authority_exceeded"
    r = analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "escalate", "version": d["application"]["version"] - 1})
    assert r.status_code == 409 and r.json()["code"] == "stale_version"
    assert analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "escalate"}).status_code == 200
    risk = login("risk@bank.test")
    low = risk.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "approve", "rate": 10})
    assert low.status_code == 422 and low.json()["code"] == "rate_below_floor"
    assert risk.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "approve", "comment": "Комитет"}).status_code == 200
    app = status(oleg, app["id"])
    assert app["status"] == "offer_issued" and app["offer"]["rate"] == 18.5 and app["offer"]["amount"] == 40_000_000


def test_s4_decline_with_reasons_and_feed(login, drain):
    ivan = login("ivan@kozlov-shop.test")
    app = create(ivan, "EXPRESS", 1_000_000, 12)
    submit(ivan, app["id"])
    drain()
    app = status(ivan, app["id"])
    assert app["status"] == "declined"
    assert {"OVERDUE_COMPANY", "TAX_ARREARS"} <= {r["code"] for r in app["explanation"]["reasons"]}
    feed = ivan.get("/api/v1/feed", params={"company_id": ivan.company["id"]}).json()
    assert any(c["id"] == "n-tax-arrears-fix" for c in feed["cards"])
    assert all(c["why"] for c in feed["cards"])


def test_s5_info_request_statement_resume(login, drain, mocks):
    elena = login("elena@cifra.test")
    app = create(elena, "EXPRESS", 2_000_000, 18)
    elena.patch(f"/api/v1/applications/{app['id']}", json={"financials": {"monthly_revenue": 2_400_000}})
    submit(elena, app["id"])
    drain()
    app = status(elena, app["id"])
    assert app["status"] == "info_requested"
    assert elena.post(f"/api/v1/applications/{app['id']}/resume").status_code == 422
    raw = elena.get(f"/api/v1/demo/sample-statement/{elena.company['id']}").content
    r = elena.post(f"/api/v1/applications/{app['id']}/documents", data={"doc_type": "bank_statement"},
                   files={"file": ("kl_to_1c.txt", raw, "text/plain")})
    assert r.status_code == 201 and r.json()["application"]["statement"]["months_covered"] == 12
    assert elena.post(f"/api/v1/applications/{app['id']}/resume").status_code == 200
    drain()
    assert status(elena, app["id"])["status"] == "offer_issued"


def test_source_outage_degrades_to_manual_review(login, drain, mocks):
    mocks.post("/admin/faults", json={"inn": "*", "source": "bki_company", "mode": "outage", "seconds": 600})
    client = login("igor@motor.test")  # у ЛогистикПро свой сценарный сбой на 40 с — здесь управляем сбоем вручную
    app = create(client, "EXPRESS", 900_000, 24)
    submit(client, app["id"])
    drain()
    analyst = login("analyst@bank.test")
    d = analyst.get(f"/api/v1/bank/applications/{app['id']}").json()
    assert d["application"]["status"] == "manual_review"
    assert next(s for s in d["sources"] if s["source"] == "bki_company")["status"] == "unavailable"
    assert sum(1 for c in d["integration_calls"] if c["source"] == "bki_company") >= 4  # повторы
    mocks.delete("/admin/faults")
    from app.integrations.client import reset_breakers
    reset_breakers()
    assert analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "rerun"}).status_code == 200
    drain()
    d = analyst.get(f"/api/v1/bank/applications/{app['id']}").json()
    assert d["application"]["status"] == "manual_review"  # повторная ручная проверка — «липкий» маршрут
    assert next(s for s in d["sources"] if s["source"] == "bki_company")["status"] == "ok"
    assert analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", json={"action": "approve"}).status_code == 200
    assert status(client, app["id"])["status"] == "offer_issued"


def test_s7_liquidation_stop_factor(login, drain):
    pavel = login("pavel@vector.test")
    app = create(pavel, "EXPRESS", 3_000_000, 12)
    submit(pavel, app["id"])
    drain()
    app = status(pavel, app["id"])
    assert app["status"] == "declined" and "STOP_COMPANY_STATUS" in {r["code"] for r in app["explanation"]["reasons"]}


def test_access_control(login):
    anna = login("anna@kofe.test")
    ivan = login("ivan@kozlov-shop.test")
    app = create(anna, "EXPRESS", 500_000, 12)
    assert ivan.get(f"/api/v1/applications/{app['id']}").status_code == 404
    assert ivan.get(f"/api/v1/companies/{anna.company['id']}").status_code == 404
    assert anna.get("/api/v1/bank/queue").status_code == 403
    analyst = login("analyst@bank.test")
    assert analyst.get(f"/api/v1/applications/{app['id']}").status_code == 403
    assert analyst.post("/api/v1/bank/policy", json={"changes": {"key_rate": 13}, "comment": "попытка"}).status_code == 403


def test_policy_versioning_changes_rates(login):
    risk = login("risk@bank.test")
    before = risk.get("/api/v1/bank/policy").json()
    r = risk.post("/api/v1/bank/policy", json={"changes": {"key_rate": 99}, "comment": "ошибка ввода"})
    assert r.status_code == 422
    r = risk.post("/api/v1/bank/policy", json={"changes": {"key_rate": 13.0}, "comment": "Снижение ключевой ставки"})
    assert r.status_code == 201 and r.json()["version"] == before["version"] + 1
    anna = login("anna@kofe.test")
    express = next(p for p in anna.get("/api/v1/products").json()["items"] if p["code"] == "EXPRESS")
    assert express["rate_from"] == 21.0
    risk.post("/api/v1/bank/policy", json={"changes": {"key_rate": before["config"]["key_rate"]}, "comment": "Возврат"})


def test_document_validation(login):
    anna = login("anna@kofe.test")
    app = create(anna, "EXPRESS", 500_000, 12)
    url = f"/api/v1/applications/{app['id']}/documents"
    assert anna.post(url, data={"doc_type": "other"}, files={"file": ("x.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    assert anna.post(url, data={"doc_type": "passport"}, files={"file": ("x.pdf", PDF, "application/pdf")}).status_code == 422
    assert anna.post(url, data={"doc_type": "other"}, files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 422
    bad_statement = anna.post(url, data={"doc_type": "bank_statement"}, files={"file": ("s.txt", b"hello", "text/plain")})
    assert bad_statement.status_code == 422 and bad_statement.json()["code"] == "statement_invalid"
    ok = anna.post(url, data={"doc_type": "other"}, files={"file": ("../../etc/passwd.pdf", PDF, "application/pdf")})
    assert ok.status_code == 201 and ok.json()["document"]["file_name"] == "passwd.pdf"


def test_audit_trail(login, stand):
    analyst = login("analyst@bank.test")
    q = analyst.get("/api/v1/bank/queue", params={"status": "all"}).json()
    analyst.get(f"/api/v1/bank/applications/{q['items'][0]['id']}")
    admin = login("admin@bank.test")
    actions = {r["action"] for r in admin.get("/api/v1/bank/audit", params={"limit": 500}).json()["items"]}
    assert {"auth.login", "dossier.viewed", "application.submitted", "contract.signed", "policy.changed"} <= actions


def test_connect_company_by_inn(login):
    new = login("new@client.test")
    assert new.post("/api/v1/companies", json={"inn": "7707083890"}).status_code == 422
    r = new.post("/api/v1/companies", json={"inn": "7707083893"})
    assert r.status_code == 201 and r.json()["ogrn"] and r.json()["membership"]["can_sign"]
    assert new.post("/api/v1/companies", json={"inn": "5027841264"}).status_code == 409  # уже подключена другими


def test_expire_overdue_offer(login, drain, stand):
    from app.models import Offer
    from app.services.common import utcnow
    from app.services.pipeline import expire_overdue

    elena = login("elena@cifra.test")
    apps = elena.get("/api/v1/applications").json()["items"]
    target = next(a for a in apps if a["status"] == "offer_issued")
    with stand["factory"]() as s:
        s.execute(update(Offer).where(Offer.status == "active").values(expires_at=utcnow() - timedelta(minutes=1)))
        s.commit()
        assert expire_overdue(s) >= 1
        s.commit()
    assert status(elena, target["id"])["status"] == "expired"


def test_dashboard_and_monitoring(login):
    admin = login("admin@bank.test")
    d = admin.get("/api/v1/bank/dashboard").json()
    assert d["kpi"]["submitted"] >= 5 and d["funnel"][0]["value"] == d["kpi"]["submitted"]
    sysinfo = admin.get("/api/v1/bank/system").json()
    assert sysinfo["jobs_by_status"].get("done", 0) > 0


def test_assistant_and_memo(login):
    ivan = login("ivan@kozlov-shop.test")
    app = next(a for a in ivan.get("/api/v1/applications").json()["items"] if a["status"] == "declined")
    ans = ivan.post("/api/v1/assistant", json={"question": "Почему мне отказали?", "application_id": app["id"]}).json()
    assert ans["provider"] == "rules" and "Причины отказа" in ans["answer"]
    analyst = login("analyst@bank.test")
    memo = analyst.get(f"/api/v1/bank/applications/{app['id']}/memo").json()
    assert memo["markdown"].startswith("# Кредитное заключение") and "отказ" in memo["markdown"]


def test_bki_requires_signed_consent(mocks):
    r = mocks.post("/bki/v1/credit-reports", json={"subject": {"type": "company", "inn": "5027841264"}, "consent": {}})
    assert r.status_code == 422 and r.json()["detail"]["error"] == "consent_required"


def test_cancel_and_events(login, stand):
    from app.models import ApplicationEvent
    igor = login("igor@motor.test")
    app = create(igor, "EXPRESS", 600_000, 12)
    r = igor.post(f"/api/v1/applications/{app['id']}/cancel", json={"comment": "Передумал"})
    assert r.json()["status"] == "cancelled"
    with stand["factory"]() as s:
        kinds = [e.transition for e in s.execute(select(ApplicationEvent).where(
            ApplicationEvent.application_id == uuid.UUID(app["id"]))).scalars() if e.transition]
    assert kinds == ["cancel"]
