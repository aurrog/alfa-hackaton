"""Кредитный конвейер: этапы автоматической обработки заявки.

  pipeline.check     — полнота и корректность, чек-лист документов, условия продукта
  pipeline.enrich    — ЕГРЮЛ/ЕГРИП, ФНС, реестр МСП, стоп-листы, БКИ (компания и
                       собственник), АБС (обороты); сбои источников → повтор с
                       паузой, после исчерпания попыток — деградация в ручную проверку
  pipeline.score     — признаки → скоринговая карта → движок решения → маршрут
  pipeline.disburse  — выдача через АБС (идемпотентно)
  maintenance.expire — истечение сроков предложений и запросов

Каждый этап идемпотентен: если статус заявки уже не тот, задача ничего не делает.
"""

from __future__ import annotations

import copy
import logging
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.calculator import annuity_payment
from app.domain.checklist import missing_required
from app.domain.decision import DecisionContext, Recommendation, decide
from app.domain.decision.policy import Policy
from app.domain.products import eligibility
from app.domain.scoring import FeatureInputs, compute_features, load_scorecard
from app.domain.state_machine import Actor
from app.domain.statuses import AppStatus
from app.integrations.client import SOURCE_TITLES, IntegrationClient, IntegrationError, NotFoundInSource, Sources
from app.metrics import DECISIONS
from app.models import Application, CheckResult, Decision, Loan, Offer, ScoringResult, Signature, Task
from app.services import transitions
from app.services.applications import checklist_for, internal_turnover, validate_form
from app.services.common import active_policy, company_profile, months_between, product_spec, today, utcnow
from app.services.jobs import enqueue
from app.services.offers import create_offer, offer_schedule

log = logging.getLogger(__name__)


class RetryLater(Exception):
    """Временная ошибка: прогресс этапа сохраняется, задача переставляется в очередь с паузой."""

    def __init__(self, reason: str, delay_sec: float | None = None):
        super().__init__(reason)
        self.delay_sec = delay_sec


def _pause(session: Session) -> None:
    """Зафиксировать промежуточный статус и выдержать демонстрационную паузу,
    чтобы клиент видел движение заявки по этапам."""
    session.commit()
    d = get_settings().pipeline_step_delay_sec
    if d > 0:
        time.sleep(d)


def _load(session: Session, app_id) -> Application | None:
    return session.get(Application, app_id, populate_existing=True)


# =============================================================== 1. Проверка данных
def stage_check(session: Session, app_id: uuid.UUID) -> None:
    app = _load(session, app_id)
    if app is None:
        return
    if app.status == AppStatus.SUBMITTED.value:
        transitions.apply(session, app, "start_check", Actor.SYSTEM)
        _pause(session)
    if app.status != AppStatus.DATA_CHECK.value:
        return
    run_id = uuid.uuid4()
    checks: list[tuple[str, str, str, str]] = []  # code, title, result, details
    new_tasks: list[Task] = []
    open_tasks = {t.doc_type for t in session.execute(
        select(Task).where(Task.application_id == app.id, Task.status == "open")).scalars() if t.doc_type}

    errs = validate_form(app)
    checks.append(("FORM_COMPLETE", "Анкета заполнена полностью", "fail" if errs else "pass",
                   "; ".join(e["message"] for e in errs) or "Все обязательные поля заполнены"))
    for e in errs:
        new_tasks.append(Task(application_id=app.id, kind="question", title=e["message"],
                              description="Ответьте в свободной форме — специалист внесёт данные", created_by_type="system"))

    cl = checklist_for(session, app)
    missing = missing_required(cl)
    checks.append(("DOCS_CHECKLIST", "Документы по чек-листу продукта", "warn" if missing else "pass",
                   ", ".join(i["title"] for i in missing) if missing else
                   f"Требуется документов: {sum(1 for i in cl if i['required'])}, все в наличии"))
    for item in missing:
        if item["doc_type"] not in open_tasks:
            new_tasks.append(Task(application_id=app.id, kind="document", doc_type=item["doc_type"],
                                  title=f"Загрузите: {item['title']}", description=f"{item['reason']}. {item['hint']}",
                                  created_by_type="system"))

    st = app.statement
    if st and st.get("months_covered", 0) < 6 and "bank_statement" not in open_tasks and not any(
            t.doc_type == "bank_statement" for t in new_tasks):
        checks.append(("STATEMENT_PERIOD", "Период выписки", "warn", f"Покрыто {st.get('months_covered')} мес. из 6 необходимых"))
        new_tasks.append(Task(application_id=app.id, kind="document", doc_type="bank_statement",
                              title="Загрузите выписку за период не менее 6 месяцев",
                              description="Загруженная выписка покрывает слишком короткий период для оценки оборотов.",
                              created_by_type="system"))
    elif st:
        checks.append(("STATEMENT_PERIOD", "Период выписки", "pass", f"{st.get('months_covered')} мес., операций: {st.get('operations')}"))

    blockers = eligibility(product_spec(app.product), company_profile(app.company), float(app.amount), app.term_months)
    checks.append(("PRODUCT_TERMS", "Соответствие условиям продукта", "fail" if blockers else "pass",
                   "; ".join(blockers) or "Сумма, срок и профиль компании соответствуют продукту"))

    for code, title, result, details in checks:
        session.add(CheckResult(application_id=app.id, run_id=run_id, stage="validation", code=code, title=title,
                                result=result, details=details, source="Анкета и документы"))

    if blockers:
        policy = active_policy(session)
        reasons = [{"code": "PRODUCT_TERMS", "client_text": b,
                    "hint": "Подберите другой продукт в разделе «Подобрать финансирование».", "details": b} for b in blockers]
        session.add(Decision(application_id=app.id, run_id=run_id, kind="final", outcome="decline", level="auto",
                             policy_version=policy.version, reason_codes=reasons, comment="Не выполнены условия продукта"))
        app.decision_outcome = "decline"
        transitions.apply(session, app, "auto_decline", Actor.SYSTEM, notify_body="; ".join(blockers))
        DECISIONS.labels("decline", "auto").inc()
        return

    if new_tasks:
        for t in new_tasks:
            session.add(t)
        titles = "; ".join(t.title for t in new_tasks)
        transitions.apply(session, app, "request_info", Actor.SYSTEM, comment=titles, notify_body=titles)
        return

    app.enrichment = {"pass": uuid.uuid4().hex, "sources": {}}
    transitions.apply(session, app, "start_enrichment", Actor.SYSTEM)
    enqueue(session, "pipeline.enrich", app.id, dedup_key=f"enrich:{app.id}:{app.enrichment['pass']}")


# =============================================================== 2. Обогащение
def _consent(session: Session, app: Application, kind: str) -> dict:
    sig = session.execute(select(Signature).where(Signature.application_id == app.id, Signature.document_kind == kind)
                          .order_by(Signature.signed_at.desc())).scalars().first()
    if sig is None:
        return {}
    return {"id": str(sig.id), "signed_at": sig.signed_at.isoformat(), "hash": sig.document_hash,
            "purpose": "Рассмотрение заявки на кредит"}


def stage_enrich(session: Session, app_id: uuid.UUID, last_attempt: bool) -> None:
    app = _load(session, app_id)
    if app is None or app.status != AppStatus.ENRICHMENT.value:
        return
    company = app.company
    form = app.form or {}
    enr = copy.deepcopy(app.enrichment or {})
    if "pass" not in enr:
        enr = {"pass": uuid.uuid4().hex, "sources": {}}
    sources: dict = enr.setdefault("sources", {})
    src = Sources(IntegrationClient(session, app.id))
    pending: list[IntegrationError] = []
    now = utcnow().isoformat()

    def fetch(name: str, fn):
        cur = sources.get(name) or {}
        if cur.get("status") in ("ok", "not_found"):
            return cur.get("data")
        try:
            data = fn()
            sources[name] = {"status": "ok" if data is not None else "not_found", "at": now, "data": data}
            return data
        except NotFoundInSource:
            sources[name] = {"status": "not_found", "at": now, "data": None}
            return None
        except IntegrationError as e:
            if e.retryable and not last_attempt:
                pending.append(e)
                sources[name] = {"status": "retrying", "at": now, "error": str(e)}
            else:
                sources[name] = {"status": "unavailable", "at": now, "error": str(e)}
            return None

    inn = company.inn
    egrul = fetch("egrul", lambda: src.egrul(inn))
    fetch("fns", lambda: src.fns(inn))
    fetch("msp", lambda: src.msp(inn))
    g = form.get("guarantor") or {}
    director = (egrul or {}).get("director") or {}
    persons = [p for p in ({"name": director.get("full_name"), "inn": director.get("inn")},
                           {"name": g.get("full_name"), "inn": g.get("inn")}) if p["name"]]
    fetch("aml", lambda: src.aml(inn, persons))
    if company.legal_form == "LE":
        fetch("bki_company", lambda: src.bki("bki_company", {"type": "company", "inn": inn, "name": company.short_name},
                                             _consent(session, app, "consent_bki_company")))
        fetch("bki_owner", lambda: src.bki("bki_owner", {"type": "person", "inn": g.get("inn"), "name": g.get("full_name"),
                                                         "birth_date": g.get("birth_date")},
                                           _consent(session, app, "consent_bki_owner")))
    else:
        fetch("bki_company", lambda: src.bki("bki_company", {"type": "entrepreneur", "inn": inn, "name": company.short_name},
                                             _consent(session, app, "consent_bki_company")))
    fetch("abs_client", lambda: src.abs_client(inn))

    app.enrichment = enr
    if pending:
        names = ", ".join(SOURCE_TITLES.get(e.source, e.source) for e in pending)
        transitions.add_event(session, app, "integration", f"Источник временно недоступен: {names}",
                              details="Повторный запрос будет выполнен автоматически", visibility="bank")
        raise RetryLater(f"sources unavailable: {names}")

    unavailable = [k for k, v in sources.items() if v.get("status") == "unavailable"]
    if unavailable:
        transitions.add_event(session, app, "integration", "Часть сведений не получена: " +
                              ", ".join(SOURCE_TITLES.get(k, k) for k in unavailable),
                              details="Заявка будет передана на ручную проверку", visibility="bank")
    _refresh_company(app, egrul, sources)
    enr["unavailable"] = unavailable
    enr["fetched_at"] = now
    app.enrichment = enr
    transitions.add_event(session, app, "integration", "Получены сведения из внешних источников",
                          details=", ".join(f"{SOURCE_TITLES.get(k, k)}: {v.get('status')}" for k, v in sources.items()),
                          visibility="bank")
    transitions.apply(session, app, "start_scoring", Actor.SYSTEM)
    enqueue(session, "pipeline.score", app.id, delay_sec=get_settings().pipeline_step_delay_sec,
            dedup_key=f"score:{app.id}:{enr['pass']}")


def _refresh_company(app: Application, egrul: dict | None, sources: dict) -> None:
    """Актуализация карточки клиента по свежей выписке ЕГРЮЛ."""
    if not egrul:
        return
    c = app.company
    c.status = (egrul.get("status") or {}).get("code", c.status)
    c.address = (egrul.get("address") or {}).get("full", c.address)
    okv = egrul.get("okved_main") or {}
    c.okved_code, c.okved_name = okv.get("code", c.okved_code), okv.get("name", c.okved_name)
    c.registry_snapshot = {**(c.registry_snapshot or {}), **egrul}
    c.registry_checked_at = utcnow()
    msp = (sources.get("msp") or {}).get("data") or {}
    if msp:
        c.msp_category = msp.get("category") if msp.get("in_registry") else None


# =============================================================== 3. Скоринг и решение
def derive(app: Application, policy: Policy) -> dict:
    """Нормализация сведений из источников в показатели для скоринга и решения."""
    enr = app.enrichment or {}
    s = enr.get("sources") or {}

    def data(name):
        v = s.get(name) or {}
        return v.get("data") if v.get("status") == "ok" else None

    egrul, fns, msp, aml = data("egrul") or {}, data("fns"), data("msp"), data("aml")
    bki_c, bki_o, abs_data = data("bki_company"), data("bki_owner"), data("abs_client")
    form = app.form or {}
    fin = form.get("financials") or {}
    company = app.company
    unavailable = list(enr.get("unavailable") or [])

    it = internal_turnover(abs_data)
    st = app.statement if app.statement and app.statement.get("months_covered", 0) >= 6 else None
    declared_monthly = fin.get("monthly_revenue") or ((fin.get("revenue_last_year") or 0) / 12 or None)
    if it and it["months"] >= 6:
        monthly, source, vol = it["avg_monthly"], "обороты в банке", it["volatility"]
    elif st:
        monthly, source, vol = st["avg_monthly_incoming"], "выписка", st.get("turnover_volatility")
    elif fns and fns.get("revenue"):
        monthly, source, vol = fns["revenue"] / 12, "ФНС (отчётность)", None
    else:
        monthly, source, vol = declared_monthly, "анкета", None
    annual = fns["revenue"] if fns and fns.get("revenue") else (monthly * 12 if monthly else None)

    if bki_c:
        existing = sum(lo.get("monthly_payment", 0) for lo in bki_c.get("active_loans", []))
    elif st:
        existing = st.get("debt_payments_monthly") or 0.0
    else:
        existing = fin.get("existing_loans_monthly_payment") or 0.0

    reg_date = egrul.get("registration_date") or (company.registration_date.isoformat() if company.registration_date else None)
    reg_date_d = date.fromisoformat(reg_date) if reg_date else None
    status = (egrul.get("status") or {}).get("code", company.status) if egrul else company.status
    mismatches = []
    reg_dir = (egrul.get("director") or {}).get("full_name")
    form_dir = (form.get("company") or {}).get("director_name")
    if reg_dir and form_dir and reg_dir.strip().lower() != form_dir.strip().lower():
        since = (egrul.get("director") or {}).get("since")
        since_txt = date.fromisoformat(since).strftime("%d.%m.%Y") if since else None
        mismatches.append(f"Руководитель в анкете «{form_dir}» не совпадает с ЕГРЮЛ «{reg_dir}»"
                          + (f" (изменение от {since_txt})" if since_txt else ""))

    company_overdue = bki_c.get("max_overdue_days_24m") if bki_c else None
    owner_overdue = bki_o.get("max_overdue_days_24m") if bki_o else (company_overdue if company.legal_form == "IP" else None)
    inquiries = max([x.get("inquiries_30d", 0) for x in (bki_c, bki_o) if x] or [0]) if (bki_c or bki_o) else None
    tax = (fns or {}).get("tax_arrears") or {}
    client_months = months_between(date.fromisoformat(abs_data["client_since"]), today()) if abs_data and abs_data.get("client_since") else 0
    return {
        "monthly_revenue": round(monthly, 2) if monthly else None,
        "revenue_source": source,
        "declared_monthly_revenue": declared_monthly,
        "annual_revenue": annual,
        "turnover_volatility": vol,
        "existing_monthly_payments": round(existing, 2),
        "registration_date": reg_date,
        "_reg_date": reg_date_d,
        "company_status": status,
        "company_status_name": (egrul.get("status") or {}).get("name") if egrul else None,
        "company_max_overdue_days": company_overdue,
        "owner_max_overdue_days": owner_overdue,
        "bki_inquiries_30d": inquiries,
        "tax_arrears": float(tax.get("amount", 0) or 0) + float(tax.get("penalties", 0) or 0),
        "okved_code": (egrul.get("okved_main") or {}).get("code") or company.okved_code,
        "bank_client_months": client_months,
        "mass_address": bool((fns or {}).get("mass_address") or (egrul.get("address") or {}).get("mass_registration")),
        "disqualified": bool((fns or {}).get("disqualified_persons")),
        "blocked_accounts": bool((fns or {}).get("blocked_accounts")),
        "aml_hit": bool(aml and aml.get("result") == "hit"),
        "in_msp_registry": bool(msp and msp.get("in_registry")) if msp is not None else bool(company.msp_category),
        "registry_mismatches": mismatches,
        "unavailable": unavailable,
    }


def build_context(app: Application, policy: Policy, d: dict) -> tuple[DecisionContext, dict]:
    spec = product_spec(app.product)
    est_rate = spec.base_rate(policy["key_rate"]) + float(policy["grade_premium"]["B"])
    new_payment = annuity_payment(float(app.amount), est_rate, app.term_months) if spec.kind == "term_loan" \
        else float(app.amount) * est_rate / 1200 + float(app.amount) / app.term_months
    fi = FeatureInputs(
        registration_date=d["_reg_date"], annual_revenue=d["annual_revenue"], turnover_volatility=d["turnover_volatility"],
        existing_monthly_payments=d["existing_monthly_payments"], new_loan_payment=new_payment,
        company_max_overdue_days=d["company_max_overdue_days"], owner_max_overdue_days=d["owner_max_overdue_days"],
        bki_inquiries_30d=d["bki_inquiries_30d"], tax_arrears=d["tax_arrears"], okved_code=d["okved_code"],
        bank_relationship_months=d["bank_client_months"],
    )
    features = compute_features(fi)
    col = (app.form or {}).get("collateral") or {}
    ctx = DecisionContext(
        product=spec, amount=float(app.amount), term=app.term_months, purpose=app.purpose,
        legal_form=app.company.legal_form, okved_code=d["okved_code"], collateral_type=col.get("type"),
        collateral_value=col.get("value"), company_status=d["company_status"], aml_hit=d["aml_hit"],
        disqualified_director=d["disqualified"], mass_address=d["mass_address"], blocked_accounts=d["blocked_accounts"],
        registry_mismatches=d["registry_mismatches"], in_msp_registry=d["in_msp_registry"],
        business_age_months=features["business_age_months"], monthly_revenue=d["monthly_revenue"],
        revenue_source=d["revenue_source"], declared_monthly_revenue=d["declared_monthly_revenue"],
        existing_monthly_payments=d["existing_monthly_payments"], company_max_overdue_days=d["company_max_overdue_days"],
        owner_max_overdue_days=d["owner_max_overdue_days"], tax_arrears=d["tax_arrears"],
        bank_client_months=d["bank_client_months"], unavailable_sources=d["unavailable"],
        sticky_manual=bool(app.sticky_manual),
    )
    return ctx, features


def stage_score(session: Session, app_id: uuid.UUID) -> None:
    app = _load(session, app_id)
    if app is None or app.status != AppStatus.SCORING.value:
        return
    run_id = uuid.uuid4()
    policy = active_policy(session)
    d = derive(app, policy)
    ctx, features = build_context(app, policy, d)
    card = load_scorecard()
    score = card.score(features)
    ctx.score = score
    session.add(ScoringResult(application_id=app.id, run_id=run_id, model_id=score.model_id,
                              model_version=score.model_version, score=score.score, pd=score.pd, grade=score.grade,
                              features=features, factors=[f.__dict__ for f in score.factors]))
    rec = decide(ctx, policy)
    for c in rec.checks:
        session.add(CheckResult(application_id=app.id, run_id=run_id, stage="policy", code=c.code, title=c.title,
                                result=c.result, effect=c.effect, details=c.details, source=c.source))
    enr = copy.deepcopy(app.enrichment or {})
    enr["derived"] = {k: v for k, v in d.items() if not k.startswith("_")}
    app.enrichment = enr
    snapshot = rec.as_dict()
    snapshot["score"] = {"score": score.score, "pd": score.pd, "grade": score.grade, "grade_title": score.grade_title,
                         "model": f"{score.model_id} {score.model_version}"}
    recommendation = Decision(
        application_id=app.id, run_id=run_id, kind="recommendation", outcome=rec.outcome, level=rec.required_level,
        policy_version=policy.version, model_version=score.model_version, amount=_dec(rec.amount), term_months=rec.term,
        rate=_dec(rec.rate), monthly_payment=_dec(rec.monthly_payment), conditions=rec.conditions,
        reason_codes=rec.reason_codes, snapshot=snapshot, decided_by_name="Кредитный движок",
        comment="; ".join(rec.manual_reasons) or None,
    )
    session.add(recommendation)
    session.flush()
    app.score, app.pd, app.risk_grade = score.score, score.pd, score.grade
    app.decision_outcome = rec.outcome
    _route(session, app, rec, policy, recommendation)


def _dec(x) -> Decimal | None:
    return None if x is None else Decimal(str(round(float(x), 2)))


def _route(session: Session, app: Application, rec: Recommendation, policy: Policy, recommendation: Decision) -> None:
    if rec.route == "auto_offer":
        final = Decision(application_id=app.id, run_id=recommendation.run_id, kind="final", outcome=rec.outcome,
                         level="auto", policy_version=policy.version, model_version=recommendation.model_version,
                         amount=_dec(rec.amount), term_months=rec.term, rate=_dec(rec.rate),
                         monthly_payment=_dec(rec.monthly_payment), conditions=rec.conditions,
                         reason_codes=rec.reason_codes, decided_by_name="Автоматическое решение")
        session.add(final)
        session.flush()
        create_offer(session, app, final, amount=rec.amount, term=rec.term, rate=rec.rate, conditions=rec.conditions,
                     changes=rec.counter_changes, policy=policy)
        transitions.apply(session, app, "auto_offer", Actor.SYSTEM,
                          payload={"amount": rec.amount, "term": rec.term, "rate": rec.rate, "outcome": rec.outcome})
        DECISIONS.labels(rec.outcome, "auto").inc()
    elif rec.route == "auto_decline":
        session.add(Decision(application_id=app.id, run_id=recommendation.run_id, kind="final", outcome="decline",
                             level="auto", policy_version=policy.version, model_version=recommendation.model_version,
                             reason_codes=rec.reason_codes, decided_by_name="Автоматическое решение"))
        transitions.apply(session, app, "auto_decline", Actor.SYSTEM,
                          notify_body="; ".join(r["client_text"] for r in rec.reason_codes) or None)
        DECISIONS.labels("decline", "auto").inc()
    else:
        app.review_level = rec.required_level
        app.manual_reasons = rec.manual_reasons
        app.sticky_manual = True
        transitions.apply(session, app, "refer", Actor.SYSTEM, comment="; ".join(rec.manual_reasons[:4]),
                          payload={"required_level": rec.required_level, "recommendation": rec.outcome})
        DECISIONS.labels("refer", "auto").inc()


# =============================================================== 4. Выдача
def stage_disburse(session: Session, app_id: uuid.UUID, last_attempt: bool) -> None:
    app = _load(session, app_id)
    if app is None or app.status != AppStatus.DISBURSEMENT.value:
        return
    offer = session.execute(select(Offer).where(Offer.application_id == app.id, Offer.status == "accepted")
                            .order_by(Offer.created_at.desc())).scalars().first()
    if offer is None:
        raise RuntimeError("accepted offer not found")
    contract = f"КД-{app.number.split('-', 1)[1]}"
    src = Sources(IntegrationClient(session, app.id))
    try:
        res = src.abs_disburse({"application_number": app.number, "contract_number": contract, "inn": app.company.inn,
                                "amount": float(offer.amount), "rate": float(offer.rate), "term_months": offer.term_months,
                                "settlement_account": app.company.settlement_account, "product": app.product.code},
                               idempotency_key=f"disburse-{app.id}")
    except IntegrationError as e:
        transitions.add_event(session, app, "integration", "АБС временно недоступна, выдача будет повторена",
                              details=str(e), visibility="bank")
        if last_attempt:
            transitions.add_event(session, app, "note", "Выдача задерживается — передано в операционный отдел",
                                  details="Попытки автоматической выдачи исчерпаны", visibility="all")
            raise
        raise RetryLater("abs unavailable") from e
    rows = offer_schedule(offer, app.product.kind)
    session.add(Loan(application_id=app.id, company_id=app.company_id, product_id=app.product_id,
                     contract_number=res.get("contract_number", contract), loan_account=res["loan_account"],
                     settlement_account=res.get("settlement_account") or app.company.settlement_account,
                     amount=offer.amount, rate=offer.rate, term_months=offer.term_months,
                     monthly_payment=offer.monthly_payment, schedule=rows, abs_reference=res["abs_reference"]))
    transitions.apply(session, app, "disbursed", Actor.SYSTEM,
                      payload={"loan_account": res["loan_account"], "abs_reference": res["abs_reference"]},
                      notify_body=f"{float(offer.amount):,.0f} ₽ зачислены на расчётный счёт. График платежей — в разделе «Кредиты».".replace(",", " "))


# =============================================================== Обслуживание сроков
def expire_overdue(session: Session) -> int:
    policy = active_policy(session)
    n = 0
    now = utcnow()
    for offer in session.execute(select(Offer).where(Offer.status.in_(["active", "accepted"]), Offer.expires_at < now)).scalars():
        app = session.get(Application, offer.application_id)
        if app and app.status in (AppStatus.OFFER_ISSUED.value, AppStatus.OFFER_ACCEPTED.value):
            offer.status = "expired"
            transitions.apply(session, app, "expire", Actor.SYSTEM, comment="Истёк срок действия предложения")
            n += 1
    limit = now - timedelta(days=int(policy["info_request_days"]))
    for app in session.execute(select(Application).where(Application.status == AppStatus.INFO_REQUESTED.value,
                                                         Application.status_changed_at < limit)).scalars():
        transitions.apply(session, app, "expire", Actor.SYSTEM, comment="Нет ответа на запрос информации")
        n += 1
    return n


HANDLERS = {
    "pipeline.check": lambda s, j, last: stage_check(s, j.application_id),
    "pipeline.enrich": lambda s, j, last: stage_enrich(s, j.application_id, last),
    "pipeline.score": lambda s, j, last: stage_score(s, j.application_id),
    "pipeline.disburse": lambda s, j, last: stage_disburse(s, j.application_id, last),
    "maintenance.expire": lambda s, j, last: expire_overdue(s),
}

__all__ = ["HANDLERS", "RetryLater", "derive", "build_context", "expire_overdue"]
