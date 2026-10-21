"""Сценарии клиента: черновик с автозаполнением, анкета, подпись и отправка,
уточнения, предложение, подписание договора."""

from __future__ import annotations

import hashlib
import json
import logging
import statistics
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.calculator import annuity_payment, max_principal
from app.domain.checklist import build_checklist
from app.domain.okved import sector_by_okved
from app.domain.products import eligibility
from app.domain.state_machine import Actor
from app.domain.statuses import CLIENT_STAGES, STATUS_META, AppStatus
from app.errors import Conflict, Forbidden, ValidationFailed
from app.integrations.client import IntegrationClient, IntegrationError, Sources
from app.models import (
    Application,
    Company,
    CompanyMember,
    Decision,
    Document,
    Offer,
    Product,
    ScoringResult,
    Signature,
    Task,
    User,
)
from app.schemas import ApplicationCreate, ApplicationPatch
from app.security import verify_password
from app.services import transitions
from app.services.access import client_company, require_signer
from app.services.audit import audit
from app.services.common import active_policy, company_profile, f, get_product, next_number, product_spec, utcnow
from app.services.jobs import enqueue

log = logging.getLogger(__name__)

CONSENT_TEXTS = {
    "consent_bki_company": "Согласие {subject} на получение банком кредитного отчёта из бюро кредитных историй "
                           "в целях рассмотрения заявки на кредит (218-ФЗ). Срок действия — 6 месяцев, при заключении "
                           "договора — на срок его действия.",
    "consent_bki_owner": "Согласие {subject} (собственника/поручителя) на получение банком кредитного отчёта "
                         "в целях рассмотрения заявки на кредит компании (218-ФЗ).",
    "consent_pd": "Согласие {subject} на обработку персональных данных в целях рассмотрения заявки (152-ФЗ).",
}


def _sha(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------ внутренние данные банка
def internal_turnover(abs_data: dict | None) -> dict | None:
    if not abs_data:
        return None
    months = abs_data.get("turnover_by_month") or []
    incoming = [m["incoming"] for m in months[-12:]]
    if not incoming:
        return None
    avg = sum(incoming) / len(incoming)
    cv = statistics.pstdev(incoming) / avg if len(incoming) > 1 and avg else None
    return {
        "months": len(incoming), "avg_monthly": round(avg, 2), "annual": round(sum(incoming) * 12 / len(incoming), 2),
        "volatility": round(cv, 4) if cv is not None else None, "client_since": abs_data.get("client_since"),
        "existing_payments": round(sum(p.get("monthly_payment", 0) for p in abs_data.get("products", [])), 2),
        "internal_overdue_days": abs_data.get("internal_max_overdue_days", 0),
    }


def fetch_internal(session: Session, company: Company, application_id=None) -> dict | None:
    if not company.is_bank_client:
        return None
    try:
        return Sources(IntegrationClient(session, application_id, retries=0)).abs_client(company.inn)
    except IntegrationError as e:
        log.warning("abs unavailable for prefill: %s", e)
        return None


# ------------------------------------------------------------------ черновик
def _guarantor_prefill(session: Session, company: Company) -> dict:
    if company.legal_form != "LE":
        return {}
    owner = session.execute(
        select(CompanyMember).where(CompanyMember.company_id == company.id, CompanyMember.is_beneficiary.is_(True))
    ).scalars().first()
    snap = company.registry_snapshot or {}
    founders = snap.get("founders") or []
    if owner is not None:
        u = owner.user
        share = next((fo.get("share") for fo in founders if fo.get("inn") == u.personal_inn), None)
        return {"full_name": u.full_name, "inn": u.personal_inn, "birth_date": u.birth_date.isoformat() if u.birth_date else None,
                "share": share}
    if founders:
        fo = max(founders, key=lambda x: x.get("share") or 0)
        return {"full_name": fo.get("name"), "inn": fo.get("inn"), "birth_date": None, "share": fo.get("share")}
    return {}


def create_draft(session: Session, user: User, data: ApplicationCreate) -> Application:
    company, m = client_company(session, user, data.company_id)
    product = get_product(session, data.product_code)
    blockers = eligibility(product_spec(product), company_profile(company))
    if blockers:
        raise ValidationFailed("Продукт недоступен для компании: " + "; ".join(blockers), code="product_not_eligible",
                               extra={"blockers": blockers})
    app = Application(
        number=next_number(session, "application", "КЗ"), company_id=company.id, product_id=product.id,
        created_by=user.id, status=AppStatus.DRAFT.value, amount=Decimal(str(data.amount)),
        term_months=data.term_months, purpose=data.purpose, preapproved=data.preapproved, form={}, prefill={},
    )
    session.add(app)
    session.flush()

    reg_src = {"source": "ЕГРЮЛ/ЕГРИП", "at": (company.registry_checked_at or utcnow()).isoformat()}
    form: dict = {
        "contact": {"name": user.full_name, "phone": user.phone, "email": user.email, "position": m.position},
        "company": {"actual_address": company.address, "employees": (company.registry_snapshot or {}).get("employees"),
                    "director_name": company.director_name, "website": None},
        "financials": {"revenue_last_year": None, "monthly_revenue": None, "net_profit_monthly": None,
                       "existing_loans_monthly_payment": None},
        "collateral": {"type": "none", "value": None, "description": None},
        "guarantor": _guarantor_prefill(session, company),
    }
    prefill: dict = {"company": reg_src, "contact": {"source": "Профиль пользователя"}}
    if form["guarantor"]:
        prefill["guarantor"] = {"source": "ЕГРЮЛ (учредители) и профиль собственника"}

    abs_data = fetch_internal(session, company, app.id)
    it = internal_turnover(abs_data)
    if it:
        form["financials"]["monthly_revenue"] = round(it["avg_monthly"], -3)
        form["financials"]["revenue_last_year"] = round(it["annual"], -3)
        form["financials"]["existing_loans_monthly_payment"] = it["existing_payments"]
        src = {"source": f"Обороты по счёту в банке за {it['months']} мес.", "at": utcnow().isoformat()}
        prefill["financials.monthly_revenue"] = src
        prefill["financials.revenue_last_year"] = src
        prefill["financials.existing_loans_monthly_payment"] = {"source": "Кредиты в банке (АБС)"}
    app.form = form
    app.prefill = prefill
    transitions.add_event(session, app, "note", "Создан черновик заявки", actor_type="client", actor=user,
                          details=f"Продукт «{product.name}», {float(data.amount):,.0f} ₽ на {data.term_months} мес.".replace(",", " "))
    return app


EDITABLE_STATUSES = {AppStatus.DRAFT.value, AppStatus.PENDING_SIGNATURE.value}


def update_draft(session: Session, user: User, app: Application, m: CompanyMember, patch: ApplicationPatch) -> Application:
    if app.status not in EDITABLE_STATUSES:
        raise Conflict("Анкету можно изменять только до отправки заявки", code="not_editable")
    if app.status == AppStatus.PENDING_SIGNATURE.value and not m.can_sign:
        raise Forbidden("Заявка передана на подпись — изменения вносит руководитель или верните её на доработку")
    data = patch.model_dump(exclude_unset=True)
    if "product_code" in data:
        product = get_product(session, data.pop("product_code"))
        app.product_id = product.id
        app.product = product
    for k in ("amount", "term_months"):
        if k in data and data[k] is not None:
            setattr(app, k, Decimal(str(data.pop(k))) if k == "amount" else data.pop(k))
    if "purpose" in data:
        app.purpose = data.pop("purpose") or "any"
    if "purpose_text" in data:
        app.purpose_text = data.pop("purpose_text")
    form = dict(app.form or {})
    prefill = dict(app.prefill or {})
    for section, values in data.items():
        if isinstance(values, dict):
            cur = dict(form.get(section) or {})
            for k, v in values.items():
                if isinstance(v, date):
                    v = v.isoformat()
                if cur.get(k) != v and f"{section}.{k}" in prefill:
                    prefill[f"{section}.{k}"] = {**prefill[f"{section}.{k}"], "edited": True}
                cur[k] = v
            form[section] = cur
        else:
            form[section] = values
    app.form = form
    app.prefill = prefill
    app.updated_at = utcnow()
    return app


# ------------------------------------------------------------------ проверки и чек-лист
def checklist_for(session: Session, app: Application) -> list[dict]:
    product = app.product
    uploaded = {d.doc_type for d in session.execute(select(Document).where(
        Document.application_id == app.id, Document.status != "rejected")).scalars()}
    has_internal = bool(app.company.is_bank_client)
    collateral = (app.form or {}).get("collateral") or {}
    return build_checklist(
        product_code=product.code, product_collateral_from=f(product.collateral_required_from),
        amount=float(app.amount), legal_form=app.company.legal_form, purpose=app.purpose,
        collateral_type=collateral.get("type"), has_internal_turnover=has_internal, uploaded_types=uploaded,
    )


def validate_form(app: Application) -> list[dict[str, str]]:
    """Ошибки, которые не дают отправить заявку (документы можно донести позже по запросу)."""
    errs: list[dict[str, str]] = []
    p = app.product
    form = app.form or {}
    amount, term = float(app.amount), app.term_months
    if not (float(p.min_amount) <= amount <= float(p.max_amount)):
        errs.append({"field": "amount", "message": f"Сумма должна быть от {float(p.min_amount):,.0f} до {float(p.max_amount):,.0f} ₽".replace(",", " ")})
    if not (p.min_term <= term <= p.max_term):
        errs.append({"field": "term_months", "message": f"Срок должен быть от {p.min_term} до {p.max_term} мес."})
    if p.purposes and app.purpose not in p.purposes and "any" not in p.purposes:
        errs.append({"field": "purpose", "message": "Цель не соответствует продукту"})
    c = form.get("contact") or {}
    if not c.get("name"):
        errs.append({"field": "contact.name", "message": "Укажите контактное лицо"})
    if not c.get("phone"):
        errs.append({"field": "contact.phone", "message": "Укажите телефон для связи"})
    fin = form.get("financials") or {}
    if not (fin.get("monthly_revenue") or fin.get("revenue_last_year")):
        errs.append({"field": "financials.monthly_revenue", "message": "Укажите выручку (за месяц или за прошлый год)"})
    col = form.get("collateral") or {}
    if col.get("type") not in (None, "none") and not col.get("value"):
        errs.append({"field": "collateral.value", "message": "Укажите оценочную стоимость залога"})
    if app.company.legal_form == "LE":
        g = form.get("guarantor") or {}
        if not g.get("full_name"):
            errs.append({"field": "guarantor.full_name", "message": "Укажите поручителя — собственника бизнеса"})
        if not g.get("inn"):
            errs.append({"field": "guarantor.inn", "message": "Укажите ИНН поручителя"})
    return errs


# ------------------------------------------------------------------ подпись и отправка
def send_for_signature(session: Session, user: User, app: Application) -> None:
    errs = validate_form(app)
    if errs:
        raise ValidationFailed("Заполните анкету перед передачей на подпись", extra={"errors": errs})
    transitions.apply(session, app, "send_for_signature", Actor.CLIENT, user)


def return_to_draft(session: Session, user: User, app: Application, comment: str | None) -> None:
    transitions.apply(session, app, "return_to_draft", Actor.CLIENT, user, comment=comment)


def _sign(session: Session, app: Application, user: User, kind: str, title: str, content: dict,
          ip: str | None, ua: str | None) -> Signature:
    sig = Signature(application_id=app.id, document_kind=kind, document_title=title, document_hash=_sha(content),
                    signer_id=user.id, signer_name=user.full_name, method="pep", ip=ip, user_agent=(ua or "")[:500])
    session.add(sig)
    return sig


def sign_and_submit(session: Session, user: User, app: Application, m: CompanyMember, password: str,
                    consent_bki: bool, consent_pd: bool, ip: str | None, ua: str | None) -> None:
    require_signer(m)
    if not verify_password(password, user.password_hash):
        audit(session, "pep.failed", user, entity_type="application", entity_id=str(app.id), ip=ip, user_agent=ua)
        raise ValidationFailed("Неверный пароль — подпись не выполнена", code="bad_signature_password")
    if not (consent_bki and consent_pd):
        raise ValidationFailed("Без согласий на запрос в БКИ и обработку данных банк не сможет рассмотреть заявку",
                               code="consents_required")
    errs = validate_form(app)
    if errs:
        raise ValidationFailed("В анкете есть ошибки", extra={"errors": errs})
    company = app.company
    form = app.form or {}
    subj = f"{company.short_name} (ИНН {company.inn})"
    snapshot = {"number": app.number, "product": app.product.code, "amount": float(app.amount),
                "term": app.term_months, "purpose": app.purpose, "form": form}
    _sign(session, app, user, "application", f"Заявка на кредит {app.number}", snapshot, ip, ua)
    _sign(session, app, user, "consent_bki_company", "Согласие на запрос кредитной истории заёмщика",
          {"text": CONSENT_TEXTS["consent_bki_company"].format(subject=subj), "app": app.number}, ip, ua)
    if company.legal_form == "LE":
        g = form.get("guarantor") or {}
        _sign(session, app, user, "consent_bki_owner", "Согласие поручителя на запрос кредитной истории",
              {"text": CONSENT_TEXTS["consent_bki_owner"].format(subject=g.get("full_name")), "app": app.number}, ip, ua)
    _sign(session, app, user, "consent_pd", "Согласие на обработку персональных данных",
          {"text": CONSENT_TEXTS["consent_pd"].format(subject=user.full_name), "app": app.number}, ip, ua)
    form["consents"] = {"bki": True, "pd": True, "signed_at": utcnow().isoformat(), "signed_by": user.full_name}
    app.form = form
    app.submitted_at = utcnow()
    app.submitted_by = user.id
    transitions.apply(session, app, "submit", Actor.CLIENT_SIGNER, user)
    enqueue(session, "pipeline.check", app.id, delay_sec=get_settings().pipeline_step_delay_sec,
            dedup_key=f"check:{app.id}:{app.version}")
    audit(session, "application.submitted", user, entity_type="application", entity_id=str(app.id), ip=ip, user_agent=ua)


def cancel(session: Session, user: User, app: Application, m: CompanyMember, comment: str | None) -> None:
    require_signer(m)
    transitions.apply(session, app, "cancel", Actor.CLIENT_SIGNER, user, comment=comment)
    for t in session.execute(select(Task).where(Task.application_id == app.id, Task.status == "open")).scalars():
        t.status = "cancelled"


# ------------------------------------------------------------------ уточнения
def answer_task(session: Session, user: User, app: Application, task: Task, text: str) -> Task:
    if app.status != AppStatus.INFO_REQUESTED.value or task.status != "open":
        raise Conflict("Задача уже закрыта")
    task.answer_text = text
    if task.kind == "question":
        task.status = "answered"
        task.answered_by = user.id
        task.answered_at = utcnow()
    transitions.add_event(session, app, "task", f"Клиент ответил на запрос: {task.title}", actor_type="client",
                          actor=user, details=text[:500])
    return task


def resume(session: Session, user: User, app: Application) -> None:
    open_tasks = session.execute(select(Task).where(Task.application_id == app.id, Task.status == "open")).scalars().all()
    if open_tasks:
        raise ValidationFailed("Выполните все задачи: " + "; ".join(t.title for t in open_tasks), code="tasks_open")
    transitions.apply(session, app, "client_answers", Actor.CLIENT, user)
    enqueue(session, "pipeline.check", app.id, delay_sec=get_settings().pipeline_step_delay_sec,
            dedup_key=f"check:{app.id}:{app.version}")


# ------------------------------------------------------------------ предложение и договор
def active_offer(session: Session, app: Application) -> Offer | None:
    return session.execute(select(Offer).where(Offer.application_id == app.id, Offer.status.in_(["active", "accepted"]))
                           .order_by(Offer.created_at.desc())).scalars().first()


def accept_offer(session: Session, user: User, app: Application, m: CompanyMember) -> Offer:
    require_signer(m)
    offer = active_offer(session, app)
    if offer is None or offer.status != "active":
        raise Conflict("Активное предложение не найдено")
    if offer.expires_at < utcnow():
        raise Conflict("Срок действия предложения истёк", code="offer_expired")
    offer.status = "accepted"
    offer.accepted_at = utcnow()
    transitions.apply(session, app, "accept_offer", Actor.CLIENT_SIGNER, user,
                      payload={"offer_id": str(offer.id), "amount": float(offer.amount)})
    return offer


def decline_offer(session: Session, user: User, app: Application, m: CompanyMember, comment: str | None) -> None:
    require_signer(m)
    offer = active_offer(session, app)
    if offer is not None:
        offer.status = "declined"
    transitions.apply(session, app, "decline_offer", Actor.CLIENT_SIGNER, user, comment=comment)


def contract_terms(app: Application, offer: Offer) -> dict:
    c = app.company
    form = app.form or {}
    return {
        "contract_number": f"КД-{app.number.split('-', 1)[1]}",
        "borrower": {"name": c.name, "inn": c.inn, "ogrn": c.ogrn, "address": c.address, "signatory": None},
        "product": app.product.name,
        "amount": float(offer.amount), "term_months": offer.term_months, "rate": float(offer.rate),
        "monthly_payment": float(offer.monthly_payment), "total_payment": float(offer.total_payment),
        "effective_rate": float(offer.effective_rate), "conditions": offer.conditions,
        "guarantor": form.get("guarantor") if c.legal_form == "LE" else None,
        "settlement_account": c.settlement_account, "purpose": app.purpose, "template_version": "2026.10",
    }


def sign_contract(session: Session, user: User, app: Application, m: CompanyMember, password: str,
                  ip: str | None, ua: str | None) -> None:
    require_signer(m)
    if not verify_password(password, user.password_hash):
        audit(session, "pep.failed", user, entity_type="application", entity_id=str(app.id), ip=ip, user_agent=ua)
        raise ValidationFailed("Неверный пароль — подпись не выполнена", code="bad_signature_password")
    offer = active_offer(session, app)
    if offer is None or offer.status != "accepted":
        raise Conflict("Нет принятого предложения")
    terms = contract_terms(app, offer)
    terms["borrower"]["signatory"] = user.full_name
    _sign(session, app, user, "loan_agreement", f"Кредитный договор {terms['contract_number']}", terms, ip, ua)
    if app.company.legal_form == "LE":
        g = (app.form or {}).get("guarantor") or {}
        _sign(session, app, user, "guarantee_agreement", f"Договор поручительства к {terms['contract_number']}",
              {"guarantor": g, "contract": terms["contract_number"]}, ip, ua)
    transitions.apply(session, app, "sign_contract", Actor.CLIENT_SIGNER, user)
    enqueue(session, "pipeline.disburse", app.id, delay_sec=get_settings().pipeline_step_delay_sec,
            dedup_key=f"disburse:{app.id}", max_attempts=6)
    audit(session, "contract.signed", user, entity_type="application", entity_id=str(app.id), ip=ip, user_agent=ua)


# ------------------------------------------------------------------ представление для клиента
def stages(app: Application, events: list) -> list[dict]:
    order = [k for k, _ in CLIENT_STAGES]
    titles = dict(CLIENT_STAGES)
    status = AppStatus(app.status)
    meta = STATUS_META[status]
    if status == AppStatus.ISSUED:
        return [{"key": k, "title": titles[k], "state": "done"} for k in order]
    ref_status = status
    if meta.terminal:
        prev = next((e.from_status for e in sorted(events, key=lambda e: e.id, reverse=True)
                     if e.kind == "status" and e.to_status == app.status), None)
        if prev:
            ref_status = AppStatus(prev)
    idx = order.index(STATUS_META[ref_status].stage)
    if status == AppStatus.OFFER_ISSUED:
        idx = order.index("signing")
    if status == AppStatus.DECLINED:
        idx = order.index("decision")
    out = []
    for i, k in enumerate(order):
        if i < idx:
            state = "done"
        elif i == idx:
            if meta.terminal:
                state = "failed" if status in (AppStatus.DECLINED, AppStatus.EXPIRED, AppStatus.CANCELLED,
                                               AppStatus.CLIENT_DECLINED) else "done"
            else:
                state = "current"
        else:
            state = "skipped" if meta.terminal else "upcoming"
        out.append({"key": k, "title": titles[k], "state": state})
    return out


def client_actions(app: Application, m: CompanyMember) -> list[str]:
    s = AppStatus(app.status)
    signer = m.can_sign
    acts: list[str] = []
    if s == AppStatus.DRAFT:
        acts += ["edit", "upload"] + (["submit", "cancel"] if signer else ["send_for_signature"])
    elif s == AppStatus.PENDING_SIGNATURE:
        acts += ["return_to_draft"] + (["edit", "upload", "submit", "cancel"] if signer else [])
    elif s == AppStatus.INFO_REQUESTED:
        acts += ["answer_tasks", "upload", "resume"] + (["cancel"] if signer else [])
    elif s in (AppStatus.MANUAL_REVIEW, AppStatus.COMMITTEE_REVIEW):
        acts += ["cancel"] if signer else []
    elif s == AppStatus.OFFER_ISSUED:
        acts += ["accept_offer", "decline_offer"] if signer else []
    elif s == AppStatus.OFFER_ACCEPTED:
        acts += ["sign_contract", "decline_offer"] if signer else []
    return acts


def next_action(app: Application, can_sign: bool) -> str | None:
    s = AppStatus(app.status)
    return {
        AppStatus.DRAFT: "Заполните анкету и отправьте заявку" if can_sign else "Заполните анкету и передайте на подпись",
        AppStatus.PENDING_SIGNATURE: "Проверьте и подпишите заявку" if can_sign else "Ждём подписи руководителя",
        AppStatus.INFO_REQUESTED: "Ответьте на запрос банка",
        AppStatus.OFFER_ISSUED: "Рассмотрите предложение банка" if can_sign else "Предложение ждёт решения руководителя",
        AppStatus.OFFER_ACCEPTED: "Подпишите кредитный договор" if can_sign else "Договор ждёт подписи руководителя",
    }.get(s)


def client_explanation(session: Session, app: Application) -> dict | None:
    s = AppStatus(app.status)
    if s not in (AppStatus.DECLINED, AppStatus.OFFER_ISSUED, AppStatus.OFFER_ACCEPTED, AppStatus.DISBURSEMENT,
                 AppStatus.ISSUED, AppStatus.CLIENT_DECLINED, AppStatus.EXPIRED):
        return None
    final = session.execute(select(Decision).where(Decision.application_id == app.id, Decision.kind == "final")
                            .order_by(Decision.created_at.desc())).scalars().first()
    if final is None:
        return None
    rec = session.execute(select(Decision).where(Decision.application_id == app.id, Decision.kind == "recommendation")
                          .order_by(Decision.created_at.desc())).scalars().first()
    expl = ((rec.snapshot or {}).get("explanation") if rec else None) or {"positives": [], "negatives": []}
    reasons = final.reason_codes or []
    plan: list[str] = []
    if final.outcome == "decline":
        for r in reasons:
            if r.get("hint") and r["hint"] not in plan:
                plan.append(r["hint"])
        for n in expl.get("negatives", []):
            if n.get("hint") and n["hint"] not in plan:
                plan.append(n["hint"])
        stop = any(r.get("code") in ("OVERDUE_COMPANY", "OVERDUE_OWNER", "TAX_ARREARS", "STOP_COMPANY_STATUS",
                                     "STOP_DISQUALIFIED") for r in reasons)
        plan = plan[:4]
        return {
            "outcome": "decline",
            "headline": "Сейчас банк не может одобрить заявку",
            "reasons": [{"code": r.get("code"), "text": r.get("client_text"), "hint": r.get("hint")} for r in reasons],
            "positives": expl.get("positives", []), "negatives": expl.get("negatives", []), "plan": plan,
            "can_reapply_after": "после устранения причин" if stop else (
                (utcnow() + timedelta(days=90)).date().isoformat()),
        }
    offer = active_offer(session, app) or session.execute(
        select(Offer).where(Offer.application_id == app.id).order_by(Offer.created_at.desc())).scalars().first()
    changes = offer.changes if offer else []
    return {
        "outcome": "counter_offer" if offer and offer.is_counter else "approve",
        "headline": "Банк готов выдать кредит на изменённых условиях" if offer and offer.is_counter
        else "Заявка одобрена на запрошенных условиях",
        "reasons": [{"code": "CHANGE", "text": c, "hint": None} for c in changes],
        "positives": expl.get("positives", []), "negatives": expl.get("negatives", []), "plan": [],
        "can_reapply_after": None,
    }


def latest_scoring(session: Session, app: Application) -> ScoringResult | None:
    return session.execute(select(ScoringResult).where(ScoringResult.application_id == app.id)
                           .order_by(ScoringResult.id.desc())).scalars().first()


# ------------------------------------------------------------------ предодобренное предложение
_preapproved_cache: dict[uuid.UUID, tuple[float, list[dict]]] = {}


def preapproved_offers(session: Session, company: Company) -> list[dict]:
    """Предодобренный лимит для клиентов банка по внутренним данным (без БКИ):
    банк уже видит обороты и платёжную дисциплину по своим продуктам.
    Лимит считается по тем же правилам посильности, что и в движке решения."""
    hit = _preapproved_cache.get(company.id)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    result: list[dict] = []
    abs_data = fetch_internal(session, company)
    it = internal_turnover(abs_data)
    if it and it["months"] >= 6 and it["internal_overdue_days"] == 0:
        policy = active_policy(session)
        p = session.execute(select(Product).where(Product.code == "EXPRESS")).scalar_one_or_none()
        if p is not None:
            spec = product_spec(p)
            if not eligibility(spec, company_profile(company, it["avg_monthly"])):
                term = 24
                rate = spec.base_rate(policy["key_rate"]) + policy["grade_premium"]["A"]
                if company_profile(company).bank_client_months >= 12:
                    rate -= float(policy["discount_bank_client"])
                ocf = it["avg_monthly"] * sector_by_okved(company.okved_code).margin * float(policy["margin_multiplier"])
                max_payment = max(ocf / float(policy["min_dscr"]) - it["existing_payments"], 0.0)
                limit = min(spec.max_amount, (spec.turnover_multiple or 2) * it["avg_monthly"] * 0.8,
                            max_principal(max_payment, rate, term) * 0.9)
                limit = max(int(limit // 100_000) * 100_000, 0)
                if limit >= spec.min_amount:
                    result.append({
                        "product_code": p.code, "product_name": p.name, "max_amount": float(limit), "term_months": term,
                        "rate_from": rate, "monthly_payment": round(annuity_payment(limit, rate, term), 2),
                        "valid_until": (utcnow() + timedelta(days=30)).date(),
                        "basis": [f"Обороты по счёту в банке: в среднем {it['avg_monthly']:,.0f} ₽ в месяц".replace(",", " "),
                                  "Без просрочек по продуктам банка",
                                  "Нужно только согласие на запрос в БКИ — документы не нужны"],
                    })
    _preapproved_cache[company.id] = (time.monotonic(), result)
    return result
