"""Преобразование моделей в ответы API (клиентские представления без внутренних данных банка)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.checklist import DOC_TYPES
from app.domain.decision.policy import Policy
from app.domain.okved import region_name, sector_by_okved
from app.domain.products import PURPOSES
from app.domain.statuses import STATUS_META, AppStatus
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    CompanyMember,
    Document,
    Loan,
    Notification,
    Offer,
    Product,
    Signature,
    Task,
    User,
)
from app.services import applications as svc
from app.services.access import ROLE_TITLES
from app.services.common import f, product_spec
from app.services.offers import offer_schedule


def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "kind": u.kind, "phone": u.phone,
        "bank_role": u.bank_role, "role_title": ROLE_TITLES.get(u.bank_role or "") if u.kind == "bank" else None,
        "position": u.position, "authority_limit": f(u.authority_limit),
    }


def company_out(c: Company, m: CompanyMember | None = None) -> dict:
    sector = sector_by_okved(c.okved_code)
    out = {
        "id": c.id, "inn": c.inn, "ogrn": c.ogrn, "kpp": c.kpp, "legal_form": c.legal_form,
        "legal_form_title": "Индивидуальный предприниматель" if c.legal_form == "IP" else "Юридическое лицо",
        "name": c.name, "short_name": c.short_name, "registration_date": c.registration_date, "address": c.address,
        "region_code": c.region_code, "region_name": region_name(c.region_code), "okved_code": c.okved_code,
        "okved_name": c.okved_name, "sector": sector.name, "status": c.status, "director_name": c.director_name,
        "msp_category": c.msp_category, "is_bank_client": c.is_bank_client, "bank_client_since": c.bank_client_since,
        "settlement_account": c.settlement_account, "registry_checked_at": c.registry_checked_at,
    }
    if m is not None:
        out["membership"] = {"role": m.role, "role_title": ROLE_TITLES.get(m.role, m.role), "can_sign": m.can_sign,
                             "position": m.position}
    return out


def product_out(p: Product, policy: Policy) -> dict:
    spec = product_spec(p)
    return {
        "code": p.code, "name": p.name, "tagline": p.tagline, "description": p.description, "kind": p.kind,
        "purposes": [{"code": c, "title": PURPOSES.get(c, {}).get("title", c)} for c in (p.purposes or [])],
        "min_amount": float(p.min_amount), "max_amount": float(p.max_amount), "min_term": p.min_term,
        "max_term": p.max_term, "rate_from": spec.base_rate(float(policy["key_rate"])),
        "rate_mode": p.rate_mode, "features": p.features or [], "decision_time": p.decision_time,
        "gov_program": p.gov_program, "collateral_required_from": f(p.collateral_required_from),
        "requires_bank_client": p.requires_bank_client, "min_business_age_months": p.min_business_age_months,
        "legal_forms": p.legal_forms or [], "auto_decision": p.auto_decision,
    }


def offer_out(o: Offer, kind: str) -> dict:
    return {
        "id": o.id, "amount": float(o.amount), "term_months": o.term_months, "rate": float(o.rate),
        "monthly_payment": float(o.monthly_payment), "total_payment": float(o.total_payment),
        "overpayment": float(o.overpayment), "effective_rate": float(o.effective_rate), "conditions": o.conditions or [],
        "changes": o.changes or [], "is_counter": o.is_counter, "status": o.status, "expires_at": o.expires_at,
        "accepted_at": o.accepted_at, "created_at": o.created_at,
        "payment_kind": "annuity" if kind == "term_loan" else "interest_only",
        "schedule": offer_schedule(o, kind),
    }


def status_block(app: Application) -> dict:
    meta = STATUS_META[AppStatus(app.status)]
    return {"status": app.status, "status_label": meta.client_label, "status_hint": meta.client_hint,
            "status_tone": meta.tone, "waiting": meta.waiting.value, "terminal": meta.terminal,
            "sla_due_at": app.sla_due_at}


def application_summary(session: Session, app: Application, m: CompanyMember) -> dict:
    offer = svc.active_offer(session, app)
    open_tasks = session.execute(select(Task.id).where(Task.application_id == app.id, Task.status == "open")).all()
    return {
        "id": app.id, "number": app.number, **status_block(app), "product_code": app.product.code,
        "product_name": app.product.name, "amount": float(app.amount), "term_months": app.term_months,
        "purpose": app.purpose, "created_at": app.created_at, "submitted_at": app.submitted_at,
        "updated_at": app.updated_at, "company_id": app.company_id, "company_name": app.company.short_name,
        "next_action": svc.next_action(app, m.can_sign), "open_tasks": len(open_tasks),
        "offer": {"amount": float(offer.amount), "term_months": offer.term_months, "rate": float(offer.rate),
                  "monthly_payment": float(offer.monthly_payment), "is_counter": offer.is_counter} if offer else None,
    }


def document_out(d: Document) -> dict:
    return {"id": d.id, "doc_type": d.doc_type, "doc_title": DOC_TYPES.get(d.doc_type, {}).get("title", d.doc_type),
            "file_name": d.file_name, "size_bytes": d.size_bytes, "content_type": d.content_type, "status": d.status,
            "review_comment": d.review_comment, "task_id": d.task_id, "created_at": d.created_at,
            "parsed": d.parsed is not None}


def client_application(session: Session, app: Application, m: CompanyMember) -> dict:
    events = session.execute(select(ApplicationEvent).where(ApplicationEvent.application_id == app.id)
                             .order_by(ApplicationEvent.id)).scalars().all()
    docs = session.execute(select(Document).where(Document.application_id == app.id)
                           .order_by(Document.created_at)).scalars().all()
    tasks = session.execute(select(Task).where(Task.application_id == app.id).order_by(Task.created_at)).scalars().all()
    sigs = session.execute(select(Signature).where(Signature.application_id == app.id)
                           .order_by(Signature.signed_at)).scalars().all()
    offer = svc.active_offer(session, app)
    if offer is None and app.status in (AppStatus.CLIENT_DECLINED.value, AppStatus.EXPIRED.value):
        offer = session.execute(select(Offer).where(Offer.application_id == app.id)
                                .order_by(Offer.created_at.desc())).scalars().first()
    loan = session.execute(select(Loan).where(Loan.application_id == app.id)).scalar_one_or_none()
    editable = app.status in svc.EDITABLE_STATUSES
    p = app.product
    statement = app.statement
    return {
        "id": app.id, "number": app.number, **status_block(app), "version": app.version,
        "company": company_out(app.company, m),
        "product": {"code": p.code, "name": p.name, "kind": p.kind, "min_amount": float(p.min_amount),
                    "max_amount": float(p.max_amount), "min_term": p.min_term, "max_term": p.max_term,
                    "purposes": p.purposes or [], "collateral_required_from": f(p.collateral_required_from)},
        "amount": float(app.amount), "term_months": app.term_months, "purpose": app.purpose,
        "purpose_title": PURPOSES.get(app.purpose, {}).get("title", app.purpose), "purpose_text": app.purpose_text,
        "preapproved": app.preapproved, "form": app.form or {}, "prefill": app.prefill or {},
        "statement": None if not statement else {
            k: statement.get(k) for k in ("format", "account", "period", "months_covered", "operations", "months",
                                          "avg_monthly_incoming", "annualized_revenue", "turnover_volatility",
                                          "debt_payments_monthly", "own_transfers_excluded", "loan_proceeds_excluded",
                                          "top_payer_share", "payers_count", "warnings")},
        "validation_errors": svc.validate_form(app) if editable else [],
        "checklist": svc.checklist_for(session, app),
        "stages": svc.stages(app, list(events)),
        "next_action": svc.next_action(app, m.can_sign),
        "actions": svc.client_actions(app, m),
        "events": [{"id": e.id, "kind": e.kind, "title": e.title, "details": e.details, "actor_type": e.actor_type,
                    "actor_name": e.actor_name if e.actor_type == "client" else None, "to_status": e.to_status,
                    "created_at": e.created_at} for e in events if e.visibility == "all"],
        "documents": [document_out(d) for d in docs],
        "tasks": [{"id": t.id, "kind": t.kind, "doc_type": t.doc_type, "title": t.title, "description": t.description,
                   "status": t.status, "answer_text": t.answer_text, "answered_at": t.answered_at,
                   "created_at": t.created_at, "from_bank": t.created_by_type == "bank"} for t in tasks
                  if t.status != "cancelled"],
        "offer": offer_out(offer, p.kind) if offer else None,
        "explanation": svc.client_explanation(session, app),
        "signatures": [{"document_kind": s.document_kind, "document_title": s.document_title,
                        "document_hash": s.document_hash, "signer_name": s.signer_name, "signed_at": s.signed_at}
                       for s in sigs],
        "loan": loan_out(loan, p) if loan else None,
        "created_at": app.created_at, "submitted_at": app.submitted_at, "decided_at": app.decided_at,
        "issued_at": app.issued_at, "updated_at": app.updated_at,
    }


def loan_out(lo: Loan, p: Product) -> dict:
    return {"id": lo.id, "application_id": lo.application_id, "contract_number": lo.contract_number,
            "loan_account": lo.loan_account, "settlement_account": lo.settlement_account, "amount": float(lo.amount),
            "rate": float(lo.rate), "term_months": lo.term_months, "monthly_payment": float(lo.monthly_payment),
            "schedule": lo.schedule or [], "status": lo.status, "issued_at": lo.issued_at,
            "product_code": p.code, "product_name": p.name, "product_kind": p.kind,
            "next_payment": next((r for r in (lo.schedule or [])), None)}


def notification_out(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
            "application_id": n.application_id, "read": n.read_at is not None, "created_at": n.created_at}
