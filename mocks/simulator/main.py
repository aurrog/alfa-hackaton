"""Симулятор внешних систем кредитного конвейера (заглушки вместо реальных сервисов).

Источники: ЕГРЮЛ/ЕГРИП, ФНС «Прозрачный бизнес», реестр МСП, стоп-листы (115-ФЗ),
бюро кредитных историй (с проверкой согласия), АБС банка (обороты клиента,
идемпотентная выдача кредита). Контракты упрощены, смысл сохранён.

Задержки и сбои управляемые: переменные MOCK_LATENCY_SCALE и MOCK_ERROR_RATE,
сценарные сбои в профилях (fixtures.py) и ручные — через /admin/faults.
Заголовок `X-Mock-Latency: 0` отключает задержку для конкретного запроса
(используется при наполнении тестовыми данными).
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from simulator import fixtures, generator
from simulator.statements import build_statement
from simulator.util import is_valid_inn, last_months, make_ogrn, rng_for, series

SOURCES = ["egrul", "fns", "msp", "aml", "bki_company", "bki_owner", "abs_client", "abs_disburse"]
LATENCY = {"egrul": (0.15, 0.4), "fns": (0.2, 0.6), "msp": (0.1, 0.3), "aml": (0.2, 0.5), "bki_company": (0.4, 1.1),
           "bki_owner": (0.3, 0.9), "abs_client": (0.05, 0.15), "abs_disburse": (0.3, 0.8)}
SCALE = float(os.getenv("MOCK_LATENCY_SCALE", "1"))
ERROR_RATE = float(os.getenv("MOCK_ERROR_RATE", "0"))

log = logging.getLogger("mocks")
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(message)s"))
log.addHandler(_h)
log.setLevel(logging.INFO)
log.propagate = False

_lock = threading.Lock()
STATE: dict[str, Any] = {
    "faults": [],  # ручные сбои: {id, inn, source, mode, until}
    "first_calls": {},  # (inn, source) → время первого вызова (сценарные сбои «с первого запроса»)
    "loans": {},  # Idempotency-Key → ответ АБС
    "loans_by_inn": defaultdict(list),  # выданные кредиты попадают в продукты клиента в АБС
    "calls": deque(maxlen=300),
}
_profiles: dict[tuple[str, date], dict] = {}

app = FastAPI(title="Симулятор внешних систем", version="1.0.0", description=__doc__, docs_url="/docs")


def profile(inn: str) -> dict:
    if not is_valid_inn(inn):
        raise HTTPException(422, detail={"error": "invalid_inn", "message": "Некорректный ИНН"})
    if inn.startswith("99"):
        raise HTTPException(404, detail={"error": "not_found", "message": "Сведения не найдены"})
    today = date.today()
    key = (inn, today)
    with _lock:
        if key not in _profiles:
            fx = fixtures.build(today)
            _profiles[key] = fx.get(inn) or generator.generate(inn, today)
        return _profiles[key]


def simulate(source: str, inn: str, request: Request) -> None:
    """Задержка, сценарные и ручные сбои, случайные ошибки."""
    rid = request.headers.get("x-request-id", "-")
    entry = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "source": source, "inn": inn,
             "request_id": rid, "result": "ok"}
    try:
        now = time.monotonic()
        with _lock:
            STATE["first_calls"].setdefault((inn, source), now)
            first = STATE["first_calls"][(inn, source)]
            manual = [f for f in STATE["faults"] if f["until"] > now and f["source"] in (source, "*")
                      and f["inn"] in (inn, "*")]
        scenario = []
        if not inn.startswith("99") and is_valid_inn(inn):
            for f in profile(inn).get("faults", []):
                if f["source"] == source and f.get("from") == "first_call" and now - first < f["seconds"]:
                    scenario.append(f)
        for f in manual + scenario:
            mode = f["mode"]
            entry["result"] = f"fault:{mode}"
            if mode == "outage":
                raise HTTPException(503, detail={"error": "service_unavailable", "message": "Сервис временно недоступен"})
            if mode == "error":
                raise HTTPException(500, detail={"error": "internal_error", "message": "Внутренняя ошибка источника"})
            if mode == "timeout":
                time.sleep(8)
                raise HTTPException(504, detail={"error": "timeout"})
            if mode == "slow":
                time.sleep(2.5)
        if request.headers.get("x-mock-latency") != "0":
            lo, hi = LATENCY.get(source, (0.1, 0.3))
            time.sleep(random.uniform(lo, hi) * SCALE)
            if ERROR_RATE and random.random() < ERROR_RATE:
                entry["result"] = "random_error"
                raise HTTPException(503, detail={"error": "service_unavailable", "message": "Случайный сбой (MOCK_ERROR_RATE)"})
    finally:
        STATE["calls"].append(entry)
        log.info(json.dumps(entry, ensure_ascii=False))


def _account(inn: str, kind: str = "settlement", salt: str = "") -> str:
    rng = rng_for(inn + salt, kind)
    prefix = {"settlement": "40802810" if len(inn) == 12 else "40702810", "loan": "45507810" if len(inn) == 12 else "45207810"}[kind]
    return prefix + "".join(str(rng.randint(0, 9)) for _ in range(12))


# ================================================================== служебное
@app.get("/health", tags=["Служебные"])
def health():
    return {"status": "ok"}


# ================================================================== ЕГРЮЛ/ЕГРИП
@app.get("/egrul/v1/entities/{inn}", tags=["ЕГРЮЛ/ЕГРИП"], summary="Выписка из ЕГРЮЛ/ЕГРИП")
def egrul(inn: str, request: Request):
    simulate("egrul", inn, request)
    p = profile(inn)
    status_code, status_name = p["status"]
    return {
        "inn": inn, "ogrn": make_ogrn(inn, p["registration_date"]), "kpp": p.get("kpp"), "type": p["type"],
        "full_name": p["full_name"], "short_name": p["short_name"], "registration_date": p["registration_date"].isoformat(),
        "address": {"full": p["address"], "region_code": p["region_code"], "mass_registration": bool(p.get("mass_address"))},
        "okved_main": {"code": p["okved"][0], "name": p["okved"][1]},
        "status": {"code": status_code, "name": status_name,
                   "since": (p.get("status_since") or p["registration_date"]).isoformat()},
        "director": {**p["director"], "since": p["director"]["since"].isoformat()},
        "founders": p.get("founders", []), "capital": None if p["type"] == "IP" else 10_000, "employees": p.get("employees"),
        "extract_date": date.today().isoformat(), "source": "ЕГРЮЛ/ЕГРИП (симулятор)",
    }


# ================================================================== ФНС
@app.get("/fns/v1/transparent-business/{inn}", tags=["ФНС"], summary="Сведения «Прозрачный бизнес»")
def fns(inn: str, request: Request):
    simulate("fns", inn, request)
    p = profile(inn)
    f = p["fns"]
    return {
        "inn": inn, "revenue": f["revenue"], "revenue_year": date.today().year - 1,
        "expenses": round(f["revenue"] * 0.9, -3), "taxes_paid": f.get("taxes_paid"), "tax_regime": f.get("tax_regime"),
        "employees_avg": p.get("employees"),
        "tax_arrears": {**f.get("tax_arrears", {"amount": 0, "penalties": 0}), "as_of": date.today().isoformat()},
        "mass_address": bool(p.get("mass_address")), "disqualified_persons": bool(f.get("disqualified_persons")),
        "blocked_accounts": bool(f.get("blocked_accounts")), "source": "ФНС России (симулятор)",
    }


# ================================================================== реестр МСП
@app.get("/msp-registry/v1/{inn}", tags=["Реестр МСП"], summary="Сведения из Единого реестра субъектов МСП")
def msp(inn: str, request: Request):
    simulate("msp", inn, request)
    p = profile(inn)
    m = p["msp"]
    return {"inn": inn, "in_registry": m["in_registry"], "category": m["category"] if m["in_registry"] else None,
            "included_at": p["registration_date"].isoformat() if m["in_registry"] else None, "source": "ФНС: реестр МСП (симулятор)"}


# ================================================================== стоп-листы
class Screening(BaseModel):
    inn: str
    persons: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/aml/v1/screening", tags=["Стоп-листы"], summary="Проверка по перечням (115-ФЗ) и внутренним стоп-листам")
def aml(body: Screening, request: Request):
    simulate("aml", body.inn, request)
    p = profile(body.inn)
    hit = p.get("aml") == "hit"
    return {"inn": body.inn, "result": "hit" if hit else "clear",
            "checked": [{"name": x.get("name"), "inn": x.get("inn"), "result": "clear"} for x in body.persons],
            "lists": ["Перечень Росфинмониторинга", "Решения МВК", "Внутренний стоп-лист банка"],
            "checked_at": datetime.now(UTC).isoformat()}


# ================================================================== БКИ
class CreditReportRequest(BaseModel):
    subject: dict[str, Any]
    consent: dict[str, Any] = Field(default_factory=dict)


def _person_report(inn: str | None) -> dict:
    if inn:
        for p in fixtures.build(date.today()).values():
            for person in p.get("persons", []):
                if person["inn"] == inn:
                    return person
    rng = rng_for(inn or "none", "person")
    return {"max_overdue_days_24m": rng.choice([0] * 8 + [5, 20]), "inquiries_30d": rng.choice([0, 0, 1, 2]),
            "active_loans": []}


@app.post("/bki/v1/credit-reports", tags=["БКИ"], summary="Кредитный отчёт (только при наличии согласия субъекта)")
def bki(body: CreditReportRequest, request: Request):
    subj = body.subject
    is_person = subj.get("type") == "person"
    source = "bki_owner" if is_person else "bki_company"
    inn = str(subj.get("inn") or "")
    simulate(source, inn or "-", request)
    if not body.consent.get("id") or not body.consent.get("signed_at"):
        raise HTTPException(422, detail={"error": "consent_required",
                                         "message": "Нет согласия субъекта на получение кредитного отчёта (218-ФЗ)"})
    if is_person:
        data = _person_report(inn)
    else:
        data = profile(inn)["bki"]
    loans = data.get("active_loans", [])
    if not is_person:
        loans = loans + [{"creditor": "Банк (наш)", "type": lo["product"], "amount": lo["amount"], "balance": lo["amount"],
                          "monthly_payment": lo["monthly_payment"]} for lo in STATE["loans_by_inn"].get(inn, [])]
    return {
        "report_id": f"BKI-{uuid.uuid4().hex[:10].upper()}", "subject": subj,
        "max_overdue_days_24m": data.get("max_overdue_days_24m", 0),
        "current_overdue_amount": 0 if data.get("max_overdue_days_24m", 0) < 90 else round(sum(lo.get("monthly_payment", 0) for lo in loans) * 2, -2),
        "inquiries_30d": data.get("inquiries_30d", 0), "active_loans": loans,
        "closed_loans_count": rng_for(inn, "closed").randint(0, 6), "consent_id": body.consent.get("id"),
        "generated_at": datetime.now(UTC).isoformat(), "source": "Бюро кредитных историй (симулятор)",
    }


# ================================================================== АБС
@app.get("/abs/v1/clients/{inn}", tags=["АБС"], summary="Клиент банка: обороты по расчётному счёту и продукты")
def abs_client(inn: str, request: Request):
    simulate("abs_client", inn, request)
    p = profile(inn)
    a = p.get("abs")
    if not a:
        raise HTTPException(404, detail={"error": "not_a_client", "message": "Не является клиентом банка"})
    months = last_months(12)
    inc = series(rng_for(inn, "abs-series"), a["avg_incoming"], a["cv"], 12, a.get("trend", 0.0), a.get("seasonal", 0.0))
    rng = rng_for(inn, "abs-out")
    products = list(a.get("products", [])) + [{"type": lo["product"], "contract_number": lo["contract_number"],
                                                "amount": lo["amount"], "monthly_payment": lo["monthly_payment"]}
                                               for lo in STATE["loans_by_inn"].get(inn, [])]
    return {
        "inn": inn, "client_since": a["client_since"].isoformat(), "settlement_account": _account(inn),
        "turnover_by_month": [{"month": m, "incoming": v, "outgoing": round(v * rng.uniform(0.82, 0.98), 2)}
                              for m, v in zip(months, inc, strict=True)],
        "products": products, "internal_max_overdue_days": a.get("internal_max_overdue_days", 0),
        "source": "АБС банка (симулятор)",
    }


class LoanRequest(BaseModel):
    application_number: str
    contract_number: str
    inn: str
    amount: float = Field(gt=0)
    rate: float = Field(ge=0)
    term_months: int = Field(gt=0)
    settlement_account: str | None = None
    product: str


@app.post("/abs/v1/loans", tags=["АБС"], summary="Открыть ссудный счёт и выдать кредит (идемпотентно)")
def abs_loan(body: LoanRequest, request: Request, idempotency_key: str | None = Header(None)):
    if not idempotency_key:
        raise HTTPException(400, detail={"error": "idempotency_key_required"})
    with _lock:
        if idempotency_key in STATE["loans"]:
            return JSONResponse(STATE["loans"][idempotency_key], headers={"Idempotent-Replayed": "true"})
    simulate("abs_disburse", body.inn, request)
    r = body.rate / 1200
    payment = body.amount * r / (1 - (1 + r) ** -body.term_months) if r else body.amount / body.term_months
    res = {"status": "issued", "contract_number": body.contract_number, "loan_account": _account(body.inn, "loan", body.contract_number),
           "settlement_account": body.settlement_account or _account(body.inn),
           "abs_reference": f"ABS-{uuid.uuid4().hex[:12].upper()}", "issued_at": datetime.now(UTC).isoformat(),
           "amount": body.amount}
    with _lock:
        if idempotency_key not in STATE["loans"]:
            STATE["loans"][idempotency_key] = res
            STATE["loans_by_inn"][body.inn].append({"product": body.product, "contract_number": body.contract_number,
                                                    "amount": body.amount, "monthly_payment": round(payment, 2)})
        return STATE["loans"][idempotency_key]


# ================================================================== демо-файлы
@app.get("/samples/statements/{inn}", tags=["Демо"], summary="Синтетическая выписка 1С (Windows-1251) для компании")
def sample_statement(inn: str):
    p = profile(inn)
    text = build_statement(inn, p)
    return Response(text.encode("cp1251"), media_type="text/plain; charset=windows-1251",
                    headers={"Content-Disposition": f'attachment; filename="kl_to_1c_{inn}.txt"'})


# ================================================================== управление сбоями
class FaultIn(BaseModel):
    inn: str = Field("*", description="ИНН или * — для всех")
    source: str = Field(..., description="egrul | fns | msp | aml | bki_company | bki_owner | abs_client | abs_disburse | *")
    mode: Literal["outage", "error", "timeout", "slow"] = "outage"
    seconds: int = Field(60, ge=1, le=3600)


@app.post("/admin/faults", tags=["Управление сбоями"], summary="Включить сбой источника на N секунд")
def add_fault(body: FaultIn):
    if body.source != "*" and body.source not in SOURCES:
        raise HTTPException(422, detail={"error": "unknown_source", "sources": SOURCES})
    f = {"id": uuid.uuid4().hex[:8], "inn": body.inn, "source": body.source, "mode": body.mode,
         "until": time.monotonic() + body.seconds, "seconds": body.seconds}
    with _lock:
        STATE["faults"].append(f)
    return {"fault": {k: v for k, v in f.items() if k != "until"}, "active": _active_faults()}


def _active_faults() -> list[dict]:
    now = time.monotonic()
    return [{"id": f["id"], "inn": f["inn"], "source": f["source"], "mode": f["mode"],
             "remaining_sec": round(f["until"] - now, 1)} for f in STATE["faults"] if f["until"] > now]


@app.get("/admin/faults", tags=["Управление сбоями"], summary="Активные сбои")
def list_faults():
    now = time.monotonic()
    scenario = []
    for inn, p in fixtures.build(date.today()).items():
        for f in p.get("faults", []):
            first = STATE["first_calls"].get((inn, f["source"]))
            scenario.append({"inn": inn, "scenario": p["scenario"], "source": f["source"], "mode": f["mode"],
                             "window_sec": f["seconds"],
                             "state": "not_started" if first is None else ("active" if now - first < f["seconds"] else "finished")})
    return {"manual": _active_faults(), "scenario": scenario}


@app.delete("/admin/faults", tags=["Управление сбоями"], summary="Отключить все ручные сбои")
def clear_faults():
    with _lock:
        STATE["faults"].clear()
    return {"manual": []}


@app.post("/admin/reset", tags=["Управление сбоями"], summary="Сбросить состояние симулятора")
def reset():
    with _lock:
        STATE["faults"].clear()
        STATE["first_calls"].clear()
        STATE["loans"].clear()
        STATE["loans_by_inn"].clear()
        STATE["calls"].clear()
        _profiles.clear()
    return {"status": "reset"}


@app.get("/admin/calls", tags=["Управление сбоями"], summary="Последние вызовы источников")
def calls(limit: int = 100):
    return {"items": list(STATE["calls"])[-limit:][::-1]}


@app.get("/admin/scenarios", tags=["Управление сбоями"], summary="Компании сквозных сценариев")
def scenarios():
    return {"items": [{"inn": inn, "scenario": p["scenario"], "name": p["short_name"], "type": p["type"],
                       "bank_client": bool(p.get("abs")), "faults": p.get("faults", [])}
                      for inn, p in fixtures.build(date.today()).items()],
            "hint": "Любой другой корректный ИНН → сгенерированный профиль; ИНН с префиксом 99 → «не найдено»."}
