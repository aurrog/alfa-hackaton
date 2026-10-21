#!/usr/bin/env python3
"""Сквозные сценарии S1–S8 через публичный API запущенного стенда.

    pip install httpx==0.28.1
    python3 tests/e2e/run_scenarios.py --base http://localhost:8080 --mocks http://localhost:8081 [--only S1,S2]

Каждый сценарий проходит путь клиента и банка целиком и проверяет ожидаемые
статусы, суммы, ставки, причины решений и права доступа. Перед запуском
состояние симулятора сбрасывается (сценарные сбои начинаются заново).
"""

from __future__ import annotations

import argparse
import random
import sys
import time
import uuid
from pathlib import Path

import httpx

PASSWORD = "Demo-2026"
ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "test-data" / "documents"
PIPELINE = {"submitted", "data_check", "enrichment", "scoring", "disbursement"}


class Fail(AssertionError):
    pass


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise Fail(msg)


class Api:
    def __init__(self, base: str, email: str | None = None):
        self.base = base.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=30.0)
        self.user: dict = {}
        if email:
            self.login(email)

    def login(self, email: str) -> Api:
        r = self.http.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        check(r.status_code == 200, f"вход {email}: {r.status_code} {r.text[:200]}")
        body = r.json()
        self.http.headers["Authorization"] = f"Bearer {body['access_token']}"
        self.user = body["user"]
        return self

    def req(self, method: str, path: str, expect: int | tuple = (200, 201, 204), **kw) -> httpx.Response:
        r = self.http.request(method, path, **kw)
        exp = (expect,) if isinstance(expect, int) else expect
        check(r.status_code in exp, f"{method} {path}: ожидали {exp}, получили {r.status_code} {r.text[:300]}")
        return r

    def get(self, path, **kw):
        return self.req("GET", path, **kw).json()

    def post(self, path, json=None, expect=(200, 201), **kw):
        r = self.req("POST", path, expect=expect, json=json, **kw)
        return r.json() if r.content and r.headers.get("content-type", "").startswith(("application/json", "application/problem")) else None

    def patch(self, path, json, **kw):
        return self.req("PATCH", path, json=json, **kw).json()

    def company(self) -> dict:
        me = self.get("/api/v1/auth/me")
        check(me["companies"], "у пользователя нет компании")
        return me["companies"][0]

    def wait(self, app_id: str, statuses: set[str], timeout: float = 90.0) -> dict:
        t0 = time.monotonic()
        seen = []
        while True:
            app = self.get(f"/api/v1/applications/{app_id}")
            if not seen or seen[-1] != app["status"]:
                seen.append(app["status"])
            if app["status"] in statuses:
                return app
            if app["status"] not in PIPELINE and app["status"] not in statuses and time.monotonic() - t0 > 5 and \
                    app["status"] not in {"draft", "pending_signature"}:
                raise Fail(f"заявка остановилась в «{app['status']}», ждали {statuses}; путь: {' → '.join(seen)}")
            if time.monotonic() - t0 > timeout:
                raise Fail(f"таймаут ожидания {statuses}; путь: {' → '.join(seen)}")
            time.sleep(0.7)

    def wait_bank(self, app_id: str, statuses: set[str], timeout: float = 90.0) -> dict:
        t0 = time.monotonic()
        while True:
            d = self.get(f"/api/v1/bank/applications/{app_id}")
            if d["application"]["status"] in statuses:
                return d
            if time.monotonic() - t0 > timeout:
                raise Fail(f"таймаут ожидания {statuses} (сейчас {d['application']['status']})")
            time.sleep(0.7)


def doc_bytes(name: str) -> tuple[str, bytes, str]:
    p = DOCS / name
    if p.exists():
        return p.name, p.read_bytes(), "application/pdf"
    return name, b"%PDF-1.4\n% e2e synthetic document\n%%EOF\n", "application/pdf"


def upload(api: Api, app_id: str, doc_type: str, name: str, data: bytes, ctype: str) -> dict:
    r = api.req("POST", f"/api/v1/applications/{app_id}/documents", data={"doc_type": doc_type},
                files={"file": (name, data, ctype)})
    return r.json()["application"]


def submit(api: Api, app_id: str, key: str | None = None) -> dict:
    headers = {"Idempotency-Key": key or uuid.uuid4().hex}
    return api.post(f"/api/v1/applications/{app_id}/submit", {"password": PASSWORD, "consent_bki": True, "consent_pd": True},
                    headers=headers)


def accept_and_sign(api: Api, app_id: str) -> dict:
    api.post(f"/api/v1/applications/{app_id}/offer/accept", headers={"Idempotency-Key": uuid.uuid4().hex})
    html = api.req("GET", f"/api/v1/applications/{app_id}/contract").text
    check("Кредитный договор" in html, "договор не сформирован")
    api.post(f"/api/v1/applications/{app_id}/contract/sign", {"password": PASSWORD},
             headers={"Idempotency-Key": uuid.uuid4().hex})
    return api.wait(app_id, {"issued"}, 60)


def random_inn(legal: bool = True, region: str | None = None) -> str:
    """Корректный ИНН с контрольными разрядами (для S8)."""
    w10, w11, w12 = (2, 4, 10, 3, 5, 9, 4, 6, 8), (7, 2, 4, 10, 3, 5, 9, 4, 6, 8), (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    ctrl = lambda d, w: sum(a * b for a, b in zip(d, w, strict=False)) % 11 % 10  # noqa: E731
    region = region or random.choice(["16", "50", "54", "66", "77", "78"])
    if legal:
        d = [int(c) for c in region] + [random.randint(0, 9) for _ in range(7)]
        d.append(ctrl(d, w10))
    else:
        d = [int(c) for c in region] + [random.randint(0, 9) for _ in range(8)]
        d.append(ctrl(d, w11))
        d.append(ctrl(d, w12))
    return "".join(map(str, d))


# ====================================================================== сценарии
def s1(base: str, mocks: str) -> str:
    anna = Api(base, "anna@kofe.test")
    c = anna.company()
    comp = anna.get(f"/api/v1/companies/{c['id']}")
    check(comp["preapproved"], "нет предодобренного предложения клиенту банка")
    limit = comp["preapproved"][0]["max_amount"]
    rec = anna.post("/api/v1/products/recommend", {"company_id": c["id"], "purpose": "equipment", "amount": 1_500_000,
                                                    "term_months": 24})
    best = next(r for r in rec["items"] if r.get("best"))
    check(best["code"] == "EXPRESS", f"лучший продукт {best['code']}, ожидали EXPRESS")
    app = anna.post("/api/v1/applications", {"company_id": c["id"], "product_code": "EXPRESS", "amount": 1_500_000,
                                             "term_months": 24, "purpose": "equipment", "preapproved": True})
    check(app["status"] == "draft", "черновик не создан")
    check(app["form"]["financials"]["monthly_revenue"], "выручка не подставилась из оборотов")
    check("financials.monthly_revenue" in app["prefill"], "у поля выручки нет источника")
    check(not [i for i in app["checklist"] if i["required"] and not i["satisfied"]], "клиенту банка не нужны документы")
    check(not app["validation_errors"], f"анкета не готова: {app['validation_errors']}")
    key = uuid.uuid4().hex
    submit(anna, app["id"], key)
    r = anna.req("POST", f"/api/v1/applications/{app['id']}/submit",
                 json={"password": PASSWORD, "consent_bki": True, "consent_pd": True}, headers={"Idempotency-Key": key})
    check(r.headers.get("Idempotent-Replayed") == "true", "повтор с тем же Idempotency-Key выполнил действие заново")
    app = anna.wait(app["id"], {"offer_issued"})
    o = app["offer"]
    check(o["amount"] == 1_500_000 and o["term_months"] == 24, f"условия {o['amount']}/{o['term_months']}")
    check(abs(o["rate"] - 21.5) < 1e-6, f"ставка {o['rate']}, ожидали 21,5%")
    check(abs(o["monthly_payment"] - 77447.36) < 1, f"платёж {o['monthly_payment']}")
    check(len(o["schedule"]) == 24, "нет графика платежей")
    check(app["explanation"]["outcome"] == "approve", "ожидали одобрение на запрошенных условиях")
    check(sum(s["state"] == "done" for s in app["stages"]) >= 3, "маршрут не отражает прохождение этапов")
    app = accept_and_sign(anna, app["id"])
    check(app["loan"] and app["loan"]["loan_account"], "кредит не выдан в АБС")
    loans = anna.get("/api/v1/loans")["items"]
    check(any(lo["application_id"] == app["id"] for lo in loans), "кредит не появился в разделе «Кредиты»")
    n = anna.get("/api/v1/notifications")
    check(n["unread"] > 0, "нет уведомлений")
    return f"{app['number']}: предодобрено до {limit:,.0f} ₽ → автоодобрение 1 500 000 ₽ / 24 мес. / 21.5% → выдан".replace(",", " ").replace("21.5", "21,5")


def s2(base: str, mocks: str) -> str:
    irina = Api(base, "irina@technostroy.test")
    c = irina.company()
    check(not c["membership"]["can_sign"], "у бухгалтера не должно быть права подписи")
    app = irina.post("/api/v1/applications", {"company_id": c["id"], "product_code": "INVEST", "amount": 40_000_000,
                                              "term_months": 60, "purpose": "equipment"})
    app = irina.patch(f"/api/v1/applications/{app['id']}",
                      {"collateral": {"type": "real_estate", "value": 60_000_000, "description": "Производственный корпус, 2 400 м²"},
                       "purpose_text": "Покупка двух обрабатывающих центров с ЧПУ"})
    required = {i["doc_type"] for i in app["checklist"] if i["required"]}
    check(required == {"financial_statements", "collateral_docs", "purchase_contract"}, f"чек-лист: {required}")
    for dt, fname in (("financial_statements", "financial_statements_technostroy.pdf"),
                      ("collateral_docs", "collateral_egrn_technostroy.pdf"),
                      ("purchase_contract", "purchase_contract_technostroy.pdf")):
        name, data, ctype = doc_bytes(fname)
        app = upload(irina, app["id"], dt, name, data, ctype)
    check(all(i["satisfied"] for i in app["checklist"] if i["required"]), "документы не закрыли чек-лист")
    irina.req("POST", f"/api/v1/applications/{app['id']}/submit", expect=403,
              json={"password": PASSWORD, "consent_bki": True, "consent_pd": True})
    app = irina.post(f"/api/v1/applications/{app['id']}/send-for-signature")
    check(app["status"] == "pending_signature", "заявка не передана на подпись")

    oleg = Api(base, "oleg@technostroy.test")
    notes = oleg.get("/api/v1/notifications")["items"]
    check(any("подписи" in x["title"] and x["application_id"] == app["id"] for x in notes), "директор не получил задачу на подпись")
    g = oleg.get(f"/api/v1/applications/{app['id']}")["form"]["guarantor"]
    check(g.get("inn") == "501043321861" and g.get("share") == 70.0, f"поручитель не подставлен: {g}")
    submit(oleg, app["id"])
    oleg.wait(app["id"], {"manual_review"})

    analyst = Api(base, "analyst@bank.test")
    q = analyst.get("/api/v1/bank/queue")
    check(any(i["id"] == app["id"] for i in q["items"]), "заявки нет в очереди аналитика")
    d = analyst.get(f"/api/v1/bank/applications/{app['id']}")
    rec = d["recommendation"]
    check(rec["outcome"] == "approve", f"рекомендация {rec['outcome']}")
    check(d["application"]["risk_grade"] == "B", f"грейд {d['application']['risk_grade']}, ожидали B")
    reasons = " ".join(d["application"]["manual_reasons"])
    check("Руководитель" in reasons and "лимита автоматического" in reasons, f"основания ручной проверки: {reasons}")
    check(analyst.get(f"/api/v1/bank/applications/{app['id']}/memo")["markdown"].startswith("# Кредитное заключение"), "нет заключения")
    r = analyst.req("POST", f"/api/v1/bank/applications/{app['id']}/decision", expect=403,
                    json={"action": "approve", "version": d["application"]["version"]})
    check(r.json()["code"] == "authority_exceeded", "аналитик не должен одобрять сверх полномочий")
    analyst.req("POST", f"/api/v1/bank/applications/{app['id']}/decision", expect=409,
                json={"action": "escalate", "version": d["application"]["version"] - 1})
    analyst.post(f"/api/v1/bank/applications/{app['id']}/decision",
                 {"action": "escalate", "comment": "Сумма выше полномочий", "version": d["application"]["version"]})
    risk = Api(base, "risk@bank.test")
    q = risk.get("/api/v1/bank/queue", params={"status": "committee_review"})
    check(any(i["id"] == app["id"] for i in q["items"]), "заявки нет в очереди комитета")
    risk.post(f"/api/v1/bank/applications/{app['id']}/decision", {"action": "approve", "comment": "Одобрено комитетом"})
    app = oleg.wait(app["id"], {"offer_issued"})
    o = app["offer"]
    check(o["amount"] == 40_000_000 and o["term_months"] == 60 and abs(o["rate"] - 18.5) < 1e-6,
          f"условия комитета {o['amount']}/{o['term_months']}/{o['rate']}")
    app = accept_and_sign(oleg, app["id"])
    kinds = {s["document_kind"] for s in app["signatures"]}
    check({"loan_agreement", "guarantee_agreement", "consent_bki_owner"} <= kinds, f"подписи: {kinds}")
    return f"{app['number']}: бухгалтер → директор → аналитик (выше полномочий) → комитет → 40 млн ₽ / 60 мес. / 18,5% → выдан"


def s3(base: str, mocks: str) -> str:
    igor = Api(base, "igor@motor.test")
    c = igor.company()
    app = igor.post("/api/v1/applications", {"company_id": c["id"], "product_code": "EXPRESS", "amount": 3_000_000,
                                             "term_months": 12, "purpose": "equipment"})
    submit(igor, app["id"])
    app = igor.wait(app["id"], {"offer_issued"})
    o = app["offer"]
    check(o["is_counter"] and o["changes"], "ожидали контрпредложение")
    check(o["amount"] < 3_000_000 or o["term_months"] > 12, "условия не изменены")
    check(app["explanation"]["outcome"] == "counter_offer", "клиенту не объяснено контрпредложение")
    igor.post(f"/api/v1/applications/{app['id']}/offer/decline", {"comment": "Подумаю"})
    return f"{app['number']}: запрос 3 000 000 ₽ / 12 мес. → {o['amount']:,.0f} ₽ / {o['term_months']} мес.: {'; '.join(o['changes'])}".replace(",", " ")


def s4(base: str, mocks: str) -> str:
    ivan = Api(base, "ivan@kozlov-shop.test")
    c = ivan.company()
    feed_before = {x["id"] for x in ivan.get("/api/v1/feed", params={"company_id": c["id"]})["cards"]}
    app = ivan.post("/api/v1/applications", {"company_id": c["id"], "product_code": "EXPRESS", "amount": 1_000_000,
                                             "term_months": 12, "purpose": "working_capital"})
    submit(ivan, app["id"])
    app = ivan.wait(app["id"], {"declined"})
    codes = {r["code"] for r in app["explanation"]["reasons"]}
    check({"OVERDUE_COMPANY", "TAX_ARREARS"} <= codes, f"причины отказа: {codes}")
    check(app["explanation"]["plan"], "нет плана действий после отказа")
    feed = ivan.get("/api/v1/feed", params={"company_id": c["id"]})
    after = {x["id"] for x in feed["cards"]}
    check({"n-tax-arrears-fix", "n-credit-history"} & after, "лента не учла причины отказа")
    check(after != feed_before, "лента не изменилась после отказа")
    card = next(x for x in feed["cards"] if x["type"] == "news")
    ivan.req("POST", "/api/v1/feed/actions", params={"company_id": c["id"]}, json={"news_id": card["id"], "action": "hide"})
    check(card["id"] not in {x["id"] for x in ivan.get("/api/v1/feed", params={"company_id": c["id"]})["cards"]}, "скрытая карточка осталась")
    anna = Api(base, "anna@kofe.test")
    a_feed = {x["id"] for x in anna.get("/api/v1/feed", params={"company_id": anna.company()["id"]})["cards"]}
    check(a_feed != after, "ленты разных клиентов совпадают")
    return f"{app['number']}: отказ ({', '.join(sorted(codes))}), план из {len(app['explanation']['plan'])} шагов, лента перестроилась"


def s5(base: str, mocks: str) -> str:
    elena = Api(base, "elena@cifra.test")
    c = elena.company()
    check(not c["is_bank_client"], "компания не должна быть клиентом банка")
    app = elena.post("/api/v1/applications", {"company_id": c["id"], "product_code": "EXPRESS", "amount": 2_000_000,
                                              "term_months": 18, "purpose": "working_capital"})
    check(any(i["doc_type"] == "bank_statement" and i["required"] for i in app["checklist"]), "выписка должна быть в чек-листе")
    elena.patch(f"/api/v1/applications/{app['id']}", {"financials": {"monthly_revenue": 2_400_000, "revenue_last_year": 28_800_000}})
    submit(elena, app["id"])
    app = elena.wait(app["id"], {"info_requested"})
    task = next(t for t in app["tasks"] if t["doc_type"] == "bank_statement" and t["status"] == "open")
    elena.req("POST", f"/api/v1/applications/{app['id']}/resume", expect=422)
    raw = elena.req("GET", f"/api/v1/demo/sample-statement/{c['id']}").content
    check(raw.startswith("1CClientBankExchange".encode("cp1251")), "демо-выписка не в формате 1С")
    app = upload(elena, app["id"], "bank_statement", "kl_to_1c.txt", raw, "text/plain")
    st = app["statement"]
    check(st and st["months_covered"] >= 12 and st["format"] == "1c", f"выписка не разобрана: {st}")
    check(st["loan_proceeds_excluded"] > 0 and st["own_transfers_excluded"] > 0, "шумы выписки не исключены")
    check(next(t for t in app["tasks"] if t["id"] == task["id"])["status"] == "answered", "задача не закрылась загрузкой")
    elena.post(f"/api/v1/applications/{app['id']}/resume")
    app = elena.wait(app["id"], {"offer_issued"})
    return (f"{app['number']}: запрос выписки → 1С разобрана ({st['months_covered']} мес., {st['avg_monthly_incoming']:,.0f} ₽/мес) "
            f"→ одобрено {app['offer']['amount']:,.0f} ₽ под {app['offer']['rate']}%").replace(",", " ")


def s6(base: str, mocks: str) -> str:
    dmitry = Api(base, "dmitry@logistikpro.test")
    c = dmitry.company()
    app = dmitry.post("/api/v1/applications", {"company_id": c["id"], "product_code": "WORKING_CAPITAL", "amount": 6_000_000,
                                               "term_months": 18, "purpose": "working_capital"})
    submit(dmitry, app["id"])
    t0 = time.monotonic()
    dmitry.wait(app["id"], {"manual_review"}, 120)
    analyst = Api(base, "analyst@bank.test")
    d = analyst.get(f"/api/v1/bank/applications/{app['id']}")
    bki = next(s for s in d["sources"] if s["source"] == "bki_company")
    check(bki["status"] == "unavailable", f"БКИ: {bki['status']}, ожидали unavailable")
    check(any("БКИ" in r for r in d["application"]["manual_reasons"]), "нет основания «источник недоступен»")
    check(not any(x["outcome"] == "decline" for x in d["decisions"] if x["kind"] == "final"), "сбой источника не должен вести к отказу")
    faults = httpx.get(f"{mocks}/admin/faults", timeout=10).json()["scenario"]
    while any(f["state"] == "active" for f in faults if f["inn"] == c["inn"]):
        time.sleep(2)
        faults = httpx.get(f"{mocks}/admin/faults", timeout=10).json()["scenario"]
    analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", {"action": "rerun", "comment": "БКИ восстановилось"})
    d = analyst.wait_bank(app["id"], {"manual_review"}, 90)
    while next(s for s in d["sources"] if s["source"] == "bki_company")["status"] != "ok":
        time.sleep(1)
        d = analyst.wait_bank(app["id"], {"manual_review"}, 90)
    check(d["recommendation"]["outcome"] in ("approve", "counter_offer"), f"рекомендация {d['recommendation']['outcome']}")
    analyst.post(f"/api/v1/bank/applications/{app['id']}/decision", {"action": "approve", "comment": "Данные БКИ получены, рисков нет",
                                                                    "version": d["application"]["version"]})
    app = dmitry.wait(app["id"], {"offer_issued"})
    return f"{app['number']}: сбой БКИ → ручная проверка (не отказ) → перезапрос → одобрено аналитиком за {time.monotonic() - t0:.0f} с"


def s7(base: str, mocks: str) -> str:
    pavel = Api(base, "pavel@vector.test")
    c = pavel.company()
    app = pavel.post("/api/v1/applications", {"company_id": c["id"], "product_code": "EXPRESS", "amount": 3_000_000,
                                              "term_months": 12, "purpose": "working_capital"})
    submit(pavel, app["id"])
    app = pavel.wait(app["id"], {"declined"})
    codes = {r["code"] for r in app["explanation"]["reasons"]}
    check("STOP_COMPANY_STATUS" in codes, f"причины: {codes}")
    me = pavel.get("/api/v1/auth/me")["companies"][0]
    check(me["status"] != "active", "карточка компании не обновилась по свежему ЕГРЮЛ")
    return f"{app['number']}: свежий ЕГРЮЛ — «ликвидация» → стоп-фактор, автоматический отказ; карточка обновлена"


def s8(base: str, mocks: str) -> str:
    new = Api(base, "new@client.test")
    anon = httpx.Client(base_url=base, timeout=10)
    check(anon.get("/api/v1/auth/me").status_code == 401, "без токена должен быть 401")
    check(new.req("GET", "/api/v1/bank/queue", expect=403).status_code == 403, "клиенту не положена очередь банка")
    new.req("POST", "/api/v1/companies", expect=422, json={"inn": "7707083890"})
    new.req("POST", "/api/v1/companies", expect=404, json={"inn": random_inn(region="99")})
    comp = new.post("/api/v1/companies", {"inn": random_inn(legal=random.random() < 0.6)})
    check(comp["name"] and comp["ogrn"] and comp["okved_code"], "карточка не заполнена из реестра")
    anna = Api(base, "anna@kofe.test")
    anna_app = anna.get("/api/v1/applications")["items"][0]
    new.req("GET", f"/api/v1/applications/{anna_app['id']}", expect=404)
    rec = new.post("/api/v1/products/recommend", {"company_id": comp["id"], "purpose": "working_capital",
                                                   "amount": 1_000_000, "term_months": 12, "urgent": True})
    eligible = [r for r in rec["items"] if r["eligible"]]
    if not eligible:
        return f"{comp['short_name']}: подключена по ИНН; доступных продуктов нет — {rec['items'][0]['blockers'][0]}"
    p = eligible[0]
    app = new.post("/api/v1/applications", {"company_id": comp["id"], "product_code": p["code"], "amount": p["amount"],
                                            "term_months": p["term_months"], "purpose": "working_capital"})
    patch = {}
    if not app["form"]["financials"].get("monthly_revenue"):
        patch["financials"] = {"monthly_revenue": 1_500_000}
    if comp["legal_form"] == "LE":
        patch["guarantor"] = {"full_name": "Новиков Артём Олегович", "inn": random_inn(legal=False), "share": 100}
    if patch:
        app = new.patch(f"/api/v1/applications/{app['id']}", patch)
    for item in app["checklist"]:
        if item["required"] and not item["satisfied"]:
            if item["doc_type"] == "bank_statement":
                raw = new.req("GET", f"/api/v1/demo/sample-statement/{comp['id']}").content
                app = upload(new, app["id"], "bank_statement", "kl_to_1c.txt", raw, "text/plain")
            else:
                name, data, ctype = doc_bytes(f"{item['doc_type']}.pdf")
                app = upload(new, app["id"], item["doc_type"], name, data, ctype)
    check(not app["validation_errors"], f"анкета: {app['validation_errors']}")
    submit(new, app["id"])
    final = {"offer_issued", "declined", "manual_review", "committee_review", "info_requested"}
    app = new.wait(app["id"], final)
    return f"{comp['short_name']} (ИНН {comp['inn']}) подключена по ИНН → {p['name']} → «{app['status_label']}»"


SCENARIOS = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--mocks", default="http://localhost:8081")
    ap.add_argument("--only", default="", help="например S1,S6")
    args = ap.parse_args()
    names = [n.strip().upper() for n in args.only.split(",") if n.strip()] or list(SCENARIOS)
    try:
        httpx.post(f"{args.mocks}/admin/reset", timeout=10).raise_for_status()
    except httpx.HTTPError as e:
        print(f"⚠ симулятор недоступен ({e}); сценарные сбои могут не сработать")
    failed = 0
    t_all = time.monotonic()
    for name in names:
        t0 = time.monotonic()
        try:
            msg = SCENARIOS[name](args.base, args.mocks)
            print(f"✔ {name}  {time.monotonic() - t0:5.1f} с  {msg}", flush=True)
        except Fail as e:
            failed += 1
            print(f"✘ {name}  {time.monotonic() - t0:5.1f} с  {e}", flush=True)
        except httpx.HTTPError as e:
            failed += 1
            print(f"✘ {name}  ошибка соединения: {e}", flush=True)
    print(f"\nИтого: {len(names) - failed}/{len(names)} сценариев пройдено за {time.monotonic() - t_all:.0f} с")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
