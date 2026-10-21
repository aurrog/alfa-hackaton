"""Рабочее место банка: очередь с SLA, досье заявки, решения в рамках полномочий,
кредитный комитет, запрос информации, перезапрос источников, дашборд."""

from __future__ import annotations

import copy
import statistics
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.checklist import DOC_TYPES
from app.domain.decision.engine import REASONS, price
from app.domain.state_machine import Actor
from app.domain.statuses import ACTIVE_BANK_STATUSES, STATUS_META, AppStatus
from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.integrations.client import SOURCE_TITLES
from app.metrics import DECISIONS
from app.models import (
    Application,
    ApplicationEvent,
    CheckResult,
    Company,
    Decision,
    Document,
    IntegrationCall,
    Loan,
    Offer,
    Product,
    ScoringResult,
    Signature,
    Task,
    User,
)
from app.services import transitions
from app.services.access import COMMITTEE_ROLES, DECISION_ROLES, ROLE_TITLES, require_bank
from app.services.audit import audit
from app.services.common import active_policy, f, utcnow
from app.services.jobs import enqueue
from app.services.offers import create_offer
from app.services.pipeline import build_context, derive

LEVEL_TITLES = {"auto": "Автоматически", "analyst": "Аналитик", "senior_analyst": "Старший аналитик",
                "committee": "Кредитный комитет"}
LEVEL_RANK = {"auto": 0, "analyst": 1, "senior_analyst": 2, "committee": 3}
ROLE_LEVEL = {"analyst": "analyst", "senior_analyst": "senior_analyst", "risk_manager": "committee"}


def sla_state(app: Application) -> str:
    if not app.sla_due_at or app.status not in {s.value for s in ACTIVE_BANK_STATUSES}:
        return "none"
    left = (app.sla_due_at - utcnow()).total_seconds()
    if left < 0:
        return "breached"
    total = (STATUS_META[AppStatus(app.status)].sla_hours or 1) * 3600
    return "warning" if left < total * 0.25 else "ok"


def latest_recommendation(session: Session, app_id) -> Decision | None:
    return session.execute(select(Decision).where(Decision.application_id == app_id, Decision.kind == "recommendation")
                           .order_by(Decision.created_at.desc())).scalars().first()


# ------------------------------------------------------------------ очередь
def queue(session: Session, user: User, *, status: str | None, assigned: str | None, product: str | None,
          search: str | None, limit: int = 200) -> dict:
    require_bank(user)
    q = select(Application).join(Company, Company.id == Application.company_id).join(Product, Product.id == Application.product_id)
    if status == "active" or status is None:
        q = q.where(Application.status.in_([s.value for s in ACTIVE_BANK_STATUSES]))
    elif status == "pipeline":
        q = q.where(Application.status.in_(["submitted", "data_check", "enrichment", "scoring"]))
    elif status != "all":
        q = q.where(Application.status == status)
    else:
        q = q.where(Application.status != AppStatus.DRAFT.value)
    if assigned == "me":
        q = q.where(Application.assigned_to == user.id)
    elif assigned == "unassigned":
        q = q.where(Application.assigned_to.is_(None))
    if product:
        q = q.where(Product.code == product)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Application.number.ilike(like), Company.name.ilike(like), Company.short_name.ilike(like),
                        Company.inn.ilike(like)))
    q = q.order_by(Application.sla_due_at.asc().nulls_last(), Application.updated_at.desc()).limit(limit)
    apps = session.execute(q).scalars().unique().all()
    users = {u.id: u.full_name for u in session.execute(select(User).where(User.kind == "bank")).scalars()}
    recs: dict = {}
    if apps:
        rows = session.execute(select(Decision).where(Decision.application_id.in_([a.id for a in apps]),
                                                      Decision.kind == "recommendation").order_by(Decision.created_at)).scalars()
        for d in rows:
            recs[d.application_id] = d.outcome
    items = []
    for a in apps:
        meta = STATUS_META[AppStatus(a.status)]
        items.append({
            "id": a.id, "number": a.number, "company_name": a.company.short_name, "inn": a.company.inn,
            "product_name": a.product.name, "amount": float(a.amount), "term_months": a.term_months, "status": a.status,
            "status_label": meta.label, "status_tone": meta.tone, "risk_grade": a.risk_grade, "score": a.score,
            "review_level": a.review_level, "assigned_to": a.assigned_to, "assigned_name": users.get(a.assigned_to),
            "sla_due_at": a.sla_due_at, "sla_state": sla_state(a), "submitted_at": a.submitted_at,
            "manual_reasons": a.manual_reasons or [], "recommendation": recs.get(a.id),
        })
    counts = dict(session.execute(select(Application.status, func.count()).group_by(Application.status)).all())
    return {"items": items, "counts": counts}


# ------------------------------------------------------------------ досье
def dossier(session: Session, user: User, app_id: uuid.UUID, ip: str | None = None, ua: str | None = None) -> dict:
    require_bank(user)
    app = session.get(Application, app_id)
    if app is None:
        raise NotFound("Заявка не найдена")
    audit(session, "dossier.viewed", user, entity_type="application", entity_id=str(app.id), ip=ip, user_agent=ua)
    session.commit()
    c = app.company
    meta = STATUS_META[AppStatus(app.status)]
    scoring = session.execute(select(ScoringResult).where(ScoringResult.application_id == app.id)
                              .order_by(ScoringResult.id.desc())).scalars().first()
    rec = latest_recommendation(session, app.id)
    decisions = session.execute(select(Decision).where(Decision.application_id == app.id)
                                .order_by(Decision.created_at)).scalars().all()
    checks_q = session.execute(select(CheckResult).where(CheckResult.application_id == app.id)
                               .order_by(CheckResult.id.desc())).scalars().all()
    latest_runs: dict[str, uuid.UUID] = {}
    for ch in checks_q:
        latest_runs.setdefault(ch.stage, ch.run_id)
    checks = [ch for ch in reversed(checks_q) if latest_runs.get(ch.stage) == ch.run_id]
    calls = session.execute(select(IntegrationCall).where(IntegrationCall.application_id == app.id)
                            .order_by(IntegrationCall.id.desc()).limit(60)).scalars().all()
    events = session.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)
                             .order_by(ApplicationEvent.id)).scalars().all()
    docs = session.execute(select(Document).where(Document.application_id == app.id).order_by(Document.created_at)).scalars().all()
    tasks = session.execute(select(Task).where(Task.application_id == app.id).order_by(Task.created_at)).scalars().all()
    offers = session.execute(select(Offer).where(Offer.application_id == app.id).order_by(Offer.created_at)).scalars().all()
    sigs = session.execute(select(Signature).where(Signature.application_id == app.id).order_by(Signature.signed_at)).scalars().all()
    loan = session.execute(select(Loan).where(Loan.application_id == app.id)).scalar_one_or_none()
    assigned = session.get(User, app.assigned_to) if app.assigned_to else None
    enr = copy.deepcopy(app.enrichment or {})
    sources = enr.get("sources") or {}
    src_view = [{"source": k, "title": SOURCE_TITLES.get(k, k), "status": v.get("status"), "at": v.get("at"),
                 "error": v.get("error"), "data": v.get("data")} for k, v in sources.items()]
    policy = active_policy(session)
    snap = (rec.snapshot or {}) if rec else {}
    return {
        "application": {
            "id": app.id, "number": app.number, "status": app.status, "status_label": meta.label,
            "status_tone": meta.tone, "amount": float(app.amount), "term_months": app.term_months, "purpose": app.purpose,
            "purpose_text": app.purpose_text, "product": {"code": app.product.code, "name": app.product.name,
                                                          "kind": app.product.kind},
            "submitted_at": app.submitted_at, "decided_at": app.decided_at, "sla_due_at": app.sla_due_at,
            "sla_state": sla_state(app), "review_level": app.review_level,
            "review_level_title": LEVEL_TITLES.get(app.review_level or ""),
            "manual_reasons": app.manual_reasons or [], "risk_grade": app.risk_grade, "score": app.score,
            "pd": app.pd, "assigned_to": app.assigned_to, "assigned_name": assigned.full_name if assigned else None,
            "version": app.version, "form": app.form, "prefill": app.prefill, "statement": app.statement,
            "created_at": app.created_at,
        },
        "company": {
            "id": c.id, "name": c.name, "short_name": c.short_name, "inn": c.inn, "ogrn": c.ogrn, "kpp": c.kpp,
            "legal_form": c.legal_form, "registration_date": c.registration_date, "address": c.address,
            "okved_code": c.okved_code, "okved_name": c.okved_name, "status": c.status, "director_name": c.director_name,
            "msp_category": c.msp_category, "is_bank_client": c.is_bank_client, "bank_client_since": c.bank_client_since,
            "region_code": c.region_code,
        },
        "sources": src_view,
        "derived": enr.get("derived"),
        "scoring": None if scoring is None else {
            "score": scoring.score, "pd": scoring.pd, "grade": scoring.grade, "model": f"{scoring.model_id} {scoring.model_version}",
            "factors": scoring.factors, "features": scoring.features, "created_at": scoring.created_at,
        },
        "recommendation": None if rec is None else {
            "outcome": rec.outcome, "level": rec.level, "level_title": LEVEL_TITLES.get(rec.level), "amount": f(rec.amount),
            "term_months": rec.term_months, "rate": f(rec.rate), "monthly_payment": f(rec.monthly_payment),
            "conditions": rec.conditions, "reason_codes": rec.reason_codes, "manual_reasons": snap.get("manual_reasons", []),
            "counter_changes": snap.get("counter_changes", []), "affordability": snap.get("affordability"),
            "explanation": snap.get("explanation"), "policy_version": rec.policy_version, "model_version": rec.model_version,
            "created_at": rec.created_at,
        },
        "decisions": [{
            "id": d.id, "kind": d.kind, "outcome": d.outcome, "level": d.level, "level_title": LEVEL_TITLES.get(d.level),
            "amount": f(d.amount), "term_months": d.term_months, "rate": f(d.rate), "conditions": d.conditions,
            "reason_codes": d.reason_codes, "comment": d.comment, "decided_by_name": d.decided_by_name,
            "policy_version": d.policy_version, "model_version": d.model_version, "created_at": d.created_at,
        } for d in decisions],
        "checks": [{"stage": ch.stage, "code": ch.code, "title": ch.title, "result": ch.result, "effect": ch.effect,
                    "details": ch.details, "source": ch.source} for ch in checks],
        "integration_calls": [{"id": ic.id, "source": ic.source, "title": SOURCE_TITLES.get(ic.source, ic.source),
                               "status": ic.status, "http_status": ic.http_status, "attempt": ic.attempt,
                               "duration_ms": ic.duration_ms, "error": ic.error, "created_at": ic.created_at,
                               "request_id": ic.request_id} for ic in calls],
        "events": [{"id": e.id, "kind": e.kind, "title": e.title, "details": e.details, "from_status": e.from_status,
                    "to_status": e.to_status, "actor_type": e.actor_type, "actor_name": e.actor_name,
                    "visibility": e.visibility, "created_at": e.created_at, "payload": e.payload} for e in events],
        "documents": [{"id": d.id, "doc_type": d.doc_type, "doc_title": DOC_TYPES.get(d.doc_type, {}).get("title"),
                       "file_name": d.file_name, "size_bytes": d.size_bytes, "status": d.status, "sha256": d.sha256,
                       "review_comment": d.review_comment, "parsed": d.parsed, "created_at": d.created_at} for d in docs],
        "tasks": [{"id": t.id, "kind": t.kind, "doc_type": t.doc_type, "title": t.title, "description": t.description,
                   "status": t.status, "created_by_type": t.created_by_type, "answer_text": t.answer_text,
                   "answered_at": t.answered_at, "created_at": t.created_at} for t in tasks],
        "offers": [{"id": o.id, "amount": f(o.amount), "term_months": o.term_months, "rate": f(o.rate),
                    "monthly_payment": f(o.monthly_payment), "status": o.status, "is_counter": o.is_counter,
                    "changes": o.changes, "conditions": o.conditions, "expires_at": o.expires_at,
                    "created_at": o.created_at} for o in offers],
        "signatures": [{"document_kind": s.document_kind, "document_title": s.document_title,
                        "document_hash": s.document_hash, "signer_name": s.signer_name, "signed_at": s.signed_at,
                        "ip": s.ip} for s in sigs],
        "loan": None if loan is None else {"contract_number": loan.contract_number, "loan_account": loan.loan_account,
                                            "amount": f(loan.amount), "rate": f(loan.rate), "issued_at": loan.issued_at,
                                            "abs_reference": loan.abs_reference},
        "actions": bank_actions(app, user),
        "authority": {"limit": f(user.authority_limit), "role": user.bank_role,
                      "role_title": ROLE_TITLES.get(user.bank_role or ""),
                      "required_level": app.review_level, "required_level_title": LEVEL_TITLES.get(app.review_level or "")},
        "reason_catalog": [{"code": k, "text": v["client"]} for k, v in REASONS.items()],
        "doc_types": [{"code": k, "title": v["title"]} for k, v in DOC_TYPES.items()],
        "policy": {"version": policy.version, "key_rate": policy["key_rate"]},
    }


def bank_actions(app: Application, user: User) -> list[str]:
    role = user.bank_role
    s = app.status
    acts: list[str] = []
    if s == AppStatus.MANUAL_REVIEW.value and role in DECISION_ROLES:
        acts += ["assign", "approve", "decline", "request_info", "escalate", "rerun"]
    if s == AppStatus.COMMITTEE_REVIEW.value and role in COMMITTEE_ROLES:
        acts += ["approve", "decline", "return"]
    return acts


# ------------------------------------------------------------------ действия
def assign(session: Session, user: User, app: Application) -> None:
    require_bank(user, DECISION_ROLES)
    if app.status not in {s.value for s in ACTIVE_BANK_STATUSES}:
        raise Conflict("Заявка не ожидает рассмотрения")
    app.assigned_to = user.id
    transitions.add_event(session, app, "note", f"Заявку взял в работу: {user.full_name}", actor_type="bank",
                          actor=user, visibility="bank")


def _check_authority(session: Session, user: User, app: Application, amount: float) -> str:
    level = ROLE_LEVEL.get(user.bank_role or "")
    if level is None:
        raise Forbidden("Нет полномочий на принятие решения")
    required = app.review_level or "analyst"
    if app.status == AppStatus.COMMITTEE_REVIEW.value:
        if user.bank_role not in COMMITTEE_ROLES:
            raise Forbidden("Решение по заявке на комитете принимает риск-менеджер")
        return "committee"
    limit = f(user.authority_limit)
    if LEVEL_RANK[required] > LEVEL_RANK[level]:
        raise Forbidden(f"Решение требует уровня «{LEVEL_TITLES[required]}» — вынесите заявку на кредитный комитет",
                        code="authority_exceeded")
    if limit is not None and amount > limit:
        raise Forbidden(f"Сумма {amount:,.0f} ₽ превышает ваши полномочия ({limit:,.0f} ₽) — вынесите заявку на комитет".replace(",", " "),
                        code="authority_exceeded")
    return level


def decide(session: Session, user: User, app: Application, data) -> None:
    require_bank(user, DECISION_ROLES)
    if data.version is not None and data.version != app.version:
        raise Conflict("Заявка изменилась — обновите страницу", code="stale_version")
    action = data.action
    in_committee = app.status == AppStatus.COMMITTEE_REVIEW.value
    if app.status not in (AppStatus.MANUAL_REVIEW.value, AppStatus.COMMITTEE_REVIEW.value):
        raise Conflict("Заявка не находится на ручном рассмотрении")
    actor = Actor.COMMITTEE if in_committee else Actor.ANALYST
    policy = active_policy(session)
    rec = latest_recommendation(session, app.id)

    if action == "approve":
        amount = float(data.amount or (f(rec.amount) if rec and rec.amount else float(app.amount)))
        term = int(data.term_months or (rec.term_months if rec and rec.term_months else app.term_months))
        p = app.product
        if not (float(p.min_amount) <= amount <= float(p.max_amount)):
            raise ValidationFailed("Сумма вне лимитов продукта")
        if not (p.min_term <= term <= p.max_term):
            raise ValidationFailed("Срок вне лимитов продукта")
        if amount > float(app.amount) + 1:
            raise ValidationFailed("Нельзя одобрить сумму больше запрошенной клиентом")
        d = derive(app, policy)
        ctx, _ = build_context(app, policy, d)
        floor = price(ctx, policy, app.risk_grade or "C", bool(ctx.collateral_type and ctx.collateral_type != "none"
                                                                 and ctx.collateral_value))
        rate = float(data.rate) if data.rate is not None else (f(rec.rate) if rec and rec.rate else floor)
        if rate + 1e-9 < floor:
            raise ValidationFailed(f"Ставка не может быть ниже расчётной по политике ({floor:.2f}%)".replace(".", ","),
                                   code="rate_below_floor")
        level = _check_authority(session, user, app, amount)
        override = bool(rec and rec.outcome == "decline")
        if override and not (data.comment and len(data.comment.strip()) >= 10):
            raise ValidationFailed("Одобрение вопреки рекомендации движка требует обоснования (комментарий от 10 символов)",
                                   code="override_comment_required")
        conditions = data.conditions if data.conditions is not None else (rec.conditions if rec else [])
        changes = []
        if abs(amount - float(app.amount)) > 1:
            changes.append(f"Сумма изменена с {float(app.amount):,.0f} до {amount:,.0f} ₽".replace(",", " "))
        if term != app.term_months:
            changes.append(f"Срок изменён с {app.term_months} до {term} мес.")
        final = Decision(application_id=app.id, kind="final", outcome="counter_offer" if changes else "approve",
                         level=level, policy_version=policy.version, model_version=rec.model_version if rec else None,
                         amount=Decimal(str(amount)), term_months=term, rate=Decimal(str(rate)), conditions=conditions,
                         reason_codes=[], comment=data.comment, decided_by=user.id, decided_by_name=user.full_name,
                         snapshot={"override": override, "recommendation": rec.outcome if rec else None})
        session.add(final)
        session.flush()
        offer = create_offer(session, app, final, amount=amount, term=term, rate=rate, conditions=conditions,
                             changes=changes, policy=policy)
        final.monthly_payment = offer.monthly_payment
        app.decision_outcome = final.outcome
        transitions.apply(session, app, "committee_offer" if in_committee else "analyst_offer", actor, user,
                          comment=data.comment, payload={"amount": amount, "term": term, "rate": rate, "override": override})
        DECISIONS.labels(final.outcome, level).inc()

    elif action == "decline":
        codes = data.reason_codes or ([r["code"] for r in rec.reason_codes] if rec and rec.reason_codes else [])
        if not codes:
            raise ValidationFailed("Укажите хотя бы одну причину отказа", code="reasons_required")
        reasons = []
        for code in codes:
            r = REASONS.get(code)
            if r is None:
                raise ValidationFailed(f"Неизвестная причина: {code}")
            reasons.append({"code": code, "client_text": r["client"], "hint": r["hint"], "details": data.comment or ""})
        override = bool(rec and rec.outcome in ("approve", "counter_offer"))
        if override and not (data.comment and len(data.comment.strip()) >= 10):
            raise ValidationFailed("Отказ вопреки рекомендации движка требует обоснования (комментарий от 10 символов)",
                                   code="override_comment_required")
        level = "committee" if in_committee else ROLE_LEVEL.get(user.bank_role or "", "analyst")
        session.add(Decision(application_id=app.id, kind="final", outcome="decline", level=level,
                             policy_version=policy.version, model_version=rec.model_version if rec else None,
                             reason_codes=reasons, comment=data.comment, decided_by=user.id, decided_by_name=user.full_name,
                             snapshot={"override": override}))
        app.decision_outcome = "decline"
        transitions.apply(session, app, "committee_decline" if in_committee else "analyst_decline", actor, user,
                          comment=data.comment, notify_body="; ".join(r["client_text"] for r in reasons))
        DECISIONS.labels("decline", level).inc()

    elif action == "request_info":
        if in_committee:
            raise Conflict("Запрос информации выполняет аналитик — верните заявку на доработку")
        reqs = data.info_requests or []
        if not reqs:
            raise ValidationFailed("Укажите, какие документы или пояснения нужны")
        titles = []
        for r in reqs:
            kind = r.get("kind", "question")
            doc_type = r.get("doc_type") if kind == "document" else None
            if kind == "document" and doc_type not in DOC_TYPES:
                raise ValidationFailed(f"Неизвестный тип документа: {doc_type}")
            title = r.get("title") or (f"Загрузите: {DOC_TYPES[doc_type]['title']}" if doc_type else "Ответьте на вопрос")
            session.add(Task(application_id=app.id, kind=kind, doc_type=doc_type, title=title,
                             description=r.get("description"), created_by_type="bank", created_by=user.id))
            titles.append(title)
        app.assigned_to = app.assigned_to or user.id
        transitions.apply(session, app, "analyst_request_info", actor, user, comment=data.comment,
                          notify_body="; ".join(titles))

    elif action == "escalate":
        if in_committee:
            raise Conflict("Заявка уже на комитете")
        app.review_level = "committee"
        transitions.apply(session, app, "escalate", actor, user, comment=data.comment,
                          payload={"proposed": {"amount": data.amount, "term": data.term_months, "rate": data.rate}})

    elif action == "rerun":
        if in_committee:
            raise Conflict("Перезапрос выполняет аналитик")
        app.enrichment = {"pass": uuid.uuid4().hex, "sources": {}}
        transitions.apply(session, app, "rerun", actor, user, comment=data.comment)
        enqueue(session, "pipeline.enrich", app.id, dedup_key=f"enrich:{app.id}:{app.enrichment['pass']}")

    elif action == "return":
        if not in_committee:
            raise Conflict("Вернуть на доработку можно только с комитета")
        transitions.apply(session, app, "committee_return", actor, user, comment=data.comment)
    else:
        raise ValidationFailed("Неизвестное действие")
    audit(session, f"bank.{action}", user, entity_type="application", entity_id=str(app.id),
          details={"amount": data.amount, "term": data.term_months, "rate": data.rate, "comment": data.comment})


def review_document(session: Session, user: User, doc: Document, status: str, comment: str | None) -> None:
    require_bank(user, DECISION_ROLES)
    doc.status = status
    doc.review_comment = comment
    doc.reviewed_by = user.id
    app = session.get(Application, doc.application_id)
    transitions.add_event(session, app, "document", f"Документ {'принят' if status == 'accepted' else 'отклонён'}: {doc.file_name}",
                          actor_type="bank", actor=user, details=comment, visibility="bank")


# ------------------------------------------------------------------ дашборд
def dashboard(session: Session, user: User, days: int = 30) -> dict:
    require_bank(user)
    now = utcnow()
    since = now - timedelta(days=days)
    by_status = dict(session.execute(select(Application.status, func.count()).group_by(Application.status)).all())
    submitted = session.execute(select(Application).where(Application.submitted_at.is_not(None),
                                                          Application.submitted_at >= since)).scalars().all()
    finals = session.execute(select(Decision).where(Decision.kind == "final", Decision.created_at >= since)).scalars().all()
    final_by_app: dict = {}
    for d in sorted(finals, key=lambda d: d.created_at):
        final_by_app[d.application_id] = d
    decided = list(final_by_app.values())
    approved = [d for d in decided if d.outcome in ("approve", "counter_offer")]
    auto = [d for d in decided if d.level == "auto"]
    ttd, ttd_auto, ttd_manual = [], [], []
    for a in submitted:
        if a.decided_at and a.submitted_at:
            sec = (a.decided_at - a.submitted_at).total_seconds()
            ttd.append(sec / 60)
            fin = final_by_app.get(a.id)
            (ttd_auto if fin is not None and fin.level == "auto" else ttd_manual).append(sec)
    issued = session.execute(select(Loan).where(Loan.issued_at >= since)).scalars().all()
    breached = session.execute(select(func.count()).select_from(Application).where(
        Application.status.in_([s.value for s in ACTIVE_BANK_STATUSES]), Application.sla_due_at < now)).scalar()
    grades = dict(session.execute(select(Application.risk_grade, func.count()).where(
        Application.risk_grade.is_not(None), Application.submitted_at >= since).group_by(Application.risk_grade)).all())
    by_product = []
    for p in session.execute(select(Product).order_by(Product.sort_order)).scalars():
        apps = [a for a in submitted if a.product_id == p.id]
        dec = [final_by_app[a.id] for a in apps if a.id in final_by_app]
        appr = [d for d in dec if d.outcome in ("approve", "counter_offer")]
        by_product.append({"code": p.code, "name": p.name, "submitted": len(apps), "decided": len(dec),
                           "approved": len(appr), "approval_rate": round(len(appr) / len(dec), 3) if dec else None})
    daily: dict[str, dict] = {}
    for i in range(days):
        day = (since + timedelta(days=i + 1)).date().isoformat()
        daily[day] = {"date": day, "submitted": 0, "approved": 0, "issued_amount": 0.0}
    for a in submitted:
        k = a.submitted_at.date().isoformat()
        if k in daily:
            daily[k]["submitted"] += 1
    for d in approved:
        k = d.created_at.date().isoformat()
        if k in daily:
            daily[k]["approved"] += 1
    for lo in issued:
        k = lo.issued_at.date().isoformat()
        if k in daily:
            daily[k]["issued_amount"] += float(lo.amount)
    calls = session.execute(select(IntegrationCall.source, IntegrationCall.status, func.count()).where(
        IntegrationCall.created_at >= now - timedelta(hours=24)).group_by(IntegrationCall.source, IntegrationCall.status)).all()
    health: dict[str, dict] = {}
    for src, st, n in calls:
        h = health.setdefault(src, {"source": src, "title": SOURCE_TITLES.get(src, src), "ok": 0, "errors": 0})
        if st in ("ok", "not_found"):
            h["ok"] += n
        else:
            h["errors"] += n
    for h in health.values():
        total = h["ok"] + h["errors"]
        h["error_rate"] = round(h["errors"] / total, 3) if total else 0
    pipeline_now = sum(by_status.get(s, 0) for s in ("submitted", "data_check", "enrichment", "scoring"))
    return {
        "period_days": days,
        "kpi": {
            "submitted": len(submitted),
            "decided": len(decided),
            "approval_rate": round(len(approved) / len(decided), 3) if decided else None,
            "auto_decision_rate": round(len(auto) / len(decided), 3) if decided else None,
            "median_time_to_decision_min": round(statistics.median(ttd), 1) if ttd else None,
            "median_auto_decision_sec": round(statistics.median(ttd_auto)) if ttd_auto else None,
            "median_manual_decision_hours": round(statistics.median(ttd_manual) / 3600, 1) if ttd_manual else None,
            "issued_count": len(issued),
            "issued_amount": round(sum(float(lo.amount) for lo in issued), 2),
            "in_manual_review": by_status.get("manual_review", 0) + by_status.get("committee_review", 0),
            "sla_breached": breached,
            "in_pipeline": pipeline_now,
            "waiting_client": by_status.get("info_requested", 0) + by_status.get("offer_issued", 0) + by_status.get("offer_accepted", 0),
        },
        "funnel": [
            {"stage": "Подано", "value": len(submitted)},
            {"stage": "Решение принято", "value": len(decided)},
            {"stage": "Одобрено", "value": len(approved)},
            {"stage": "Предложение принято", "value": sum(1 for a in submitted if a.status in ("offer_accepted", "disbursement", "issued"))},
            {"stage": "Выдано", "value": sum(1 for a in submitted if a.status == "issued")},
        ],
        "by_status": [{"status": k, "label": STATUS_META[AppStatus(k)].label, "count": v} for k, v in sorted(by_status.items())],
        "outcomes": {
            "approve": sum(1 for d in decided if d.outcome == "approve"),
            "counter_offer": sum(1 for d in decided if d.outcome == "counter_offer"),
            "decline": sum(1 for d in decided if d.outcome == "decline"),
        },
        "decision_levels": {lvl: sum(1 for d in decided if d.level == lvl) for lvl in ("auto", "analyst", "senior_analyst", "committee")},
        "grades": [{"grade": g, "count": grades.get(g, 0)} for g in "ABCDE"],
        "by_product": by_product,
        "daily": list(daily.values()),
        "integration_health": sorted(health.values(), key=lambda h: h["source"]),
        "queue_load": {"manual_review": by_status.get("manual_review", 0), "committee_review": by_status.get("committee_review", 0)},
        "generated_at": now,
        "settings": {"step_delay": get_settings().pipeline_step_delay_sec},
    }
