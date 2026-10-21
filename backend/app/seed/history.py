"""История заявок для дашборда и очереди: заявки проходят через настоящий
конвейер (те же проверки, источники, скоринг и решения), затем часть из них
рассматривают аналитики и комитет, клиенты принимают предложения и подписывают
договоры. В конце метки времени равномерно «раздвигаются» на последние 30 дней.
"""

from __future__ import annotations

import logging
import random
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.domain.products import eligibility
from app.domain.validators import make_inn
from app.errors import AppError
from app.integrations.client import http_client
from app.logging_setup import log_extra
from app.models import Application, CompanyMember, User
from app.schemas import ApplicationCreate, ApplicationPatch, BankDecisionIn
from app.security import hash_password
from app.seed.run import ensure_company
from app.services import applications as svc
from app.services import bank, documents
from app.services.common import company_profile, get_product, product_spec, utcnow
from app.worker.runner import drain

log = logging.getLogger("app.seed")

REGION_PREFIXES = ["16", "18", "23", "50", "52", "54", "61", "63", "66", "68", "74", "77", "78"]
PDF = b"%PDF-1.4\n% synthetic document for demo\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

# (таблица, колонки) — все метки времени, связанные с заявкой
TIME_COLUMNS: list[tuple[str, str, list[str]]] = [
    ("applications", "id", ["created_at", "updated_at", "status_changed_at", "sla_due_at", "submitted_at",
                            "decided_at", "issued_at"]),
    ("application_events", "application_id", ["created_at"]),
    ("documents", "application_id", ["created_at"]),
    ("tasks", "application_id", ["created_at", "answered_at"]),
    ("integration_calls", "application_id", ["created_at"]),
    ("check_results", "application_id", ["created_at"]),
    ("scoring_results", "application_id", ["created_at"]),
    ("decisions", "application_id", ["created_at"]),
    ("offers", "application_id", ["created_at", "expires_at", "accepted_at"]),
    ("signatures", "application_id", ["signed_at"]),
    ("loans", "application_id", ["issued_at"]),
    ("notifications", "application_id", ["created_at"]),
    ("jobs", "application_id", ["created_at", "run_after", "finished_at", "locked_at"]),
]


def _shift(session: Session, app_id: uuid.UUID, seconds: float, after=None) -> None:
    for table, key, cols in TIME_COLUMNS:
        for col in cols:
            cond = f" AND {col} > :after" if after is not None else ""
            session.execute(text(f"UPDATE {table} SET {col} = {col} + make_interval(secs => :s) "
                                 f"WHERE {key} = :id AND {col} IS NOT NULL{cond}"),
                            {"s": seconds, "id": app_id, "after": after})


def _new_inn(rng: random.Random, session: Session) -> str:
    from app.models import Company
    while True:
        region = rng.choice(REGION_PREFIXES)
        if rng.random() < 0.45:
            inn = make_inn(region + "".join(str(rng.randint(0, 9)) for _ in range(8)))
        else:
            inn = make_inn(region + "".join(str(rng.randint(0, 9)) for _ in range(7)))
        if inn.startswith("99"):
            continue
        if session.execute(select(Company.id).where(Company.inn == inn)).first() is None:
            return inn


def _choose(rng: random.Random, session: Session, company, revenue: float) -> tuple[str, float, int, str] | None:
    options = [("EXPRESS", 0.45), ("WORKING_CAPITAL", 0.2), ("INVEST", 0.12), ("OVERDRAFT", 0.1),
               ("CREDIT_LINE", 0.06), ("GOV_KEY_RATE", 0.07)]
    for _ in range(6):
        code = rng.choices([o[0] for o in options], weights=[o[1] for o in options])[0]
        p = get_product(session, code)
        spec = product_spec(p)
        if eligibility(spec, company_profile(company)):
            continue
        mult = rng.choice([0.5, 0.8, 1.2, 1.6, 2.5, 4.0])
        amount = max(spec.min_amount, min(spec.max_amount, round(revenue * mult, -5)))
        term = rng.choice([t for t in (12, 18, 24, 24, 36, 36, 48, 60) if spec.min_term <= t <= spec.max_term] or [spec.max_term])
        purpose = rng.choice(spec.purposes)
        return code, float(amount), term, purpose
    return None


def generate(factory: sessionmaker, n: int) -> None:
    s = get_settings()
    old_delay = s.pipeline_step_delay_sec
    s.pipeline_step_delay_sec = 0
    rng = random.Random(20261021)
    password = secrets.token_urlsafe(12)
    pwd_hash = hash_password(password)
    created: list[uuid.UUID] = []
    try:
        for i in range(n):
            with factory() as session:
                try:
                    app_id = _create_one(session, rng, i, password, pwd_hash)
                except AppError as e:
                    session.rollback()
                    log_extra(log, "history application skipped", reason=str(e))
                    continue
                if app_id:
                    created.append(app_id)
            drain(factory, "seed")
        _bank_and_client_actions(factory, rng, created, password)
        drain(factory, "seed")
        _spread_in_time(factory, rng, created)
        log_extra(log, "history generated", applications=len(created))
    finally:
        s.pipeline_step_delay_sec = old_delay


def _create_one(session: Session, rng: random.Random, i: int, password: str, pwd_hash: str) -> uuid.UUID | None:
    inn = _new_inn(rng, session)
    company = ensure_company(session, inn)
    snap = company.registry_snapshot or {}
    director = snap.get("director") or {}
    user = User(email=f"client{i + 1:03d}@history.test", password_hash=pwd_hash, kind="client",
                full_name=director.get("full_name") or company.short_name, phone=f"+7 900 {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
                personal_inn=director.get("inn"))
    session.add(user)
    session.flush()
    session.add(CompanyMember(company_id=company.id, user_id=user.id, role="director" if company.legal_form == "LE" else "owner",
                              can_sign=True, is_beneficiary=True, position=director.get("position")))
    session.flush()
    abs_data = svc.fetch_internal(session, company)
    it = svc.internal_turnover(abs_data)
    revenue = it["avg_monthly"] if it else float((snap.get("employees") or 10) * 120_000)
    choice = _choose(rng, session, company, revenue)
    if choice is None:
        session.rollback()
        return None
    code, amount, term, purpose = choice
    app = svc.create_draft(session, user, ApplicationCreate(company_id=company.id, product_code=code, amount=amount,
                                                            term_months=term, purpose=purpose))
    m = session.execute(select(CompanyMember).where(CompanyMember.company_id == company.id,
                                                    CompanyMember.user_id == user.id)).scalar_one()
    patch: dict = {}
    if not it:
        declared = round(revenue * rng.uniform(0.9, 1.3), -3)
        patch["financials"] = {"monthly_revenue": declared, "revenue_last_year": declared * 12}
    collateral_from = product_spec(app.product).collateral_required_from
    if collateral_from is not None and amount >= collateral_from or rng.random() < 0.15:
        patch["collateral"] = {"type": rng.choice(["real_estate", "equipment", "vehicle"]),
                               "value": round(amount * rng.uniform(1.2, 2.0), -5), "description": "Синтетический залог"}
    if patch:
        svc.update_draft(session, user, app, m, ApplicationPatch(**patch))
    statement_skipped = False
    for item in svc.checklist_for(session, app):
        if not item["required"] or item["satisfied"]:
            continue
        if item["doc_type"] == "bank_statement":
            if rng.random() < 0.15:
                statement_skipped = True
                continue
            raw = http_client().get(f"/samples/statements/{company.inn}").content
            documents.upload(session, user, app, "bank_statement", "kl_to_1c.txt", "text/plain", raw)
        else:
            documents.upload(session, user, app, item["doc_type"], f"{item['doc_type']}.pdf", "application/pdf", PDF)
    svc.sign_and_submit(session, user, app, m, password, True, True, "10.0.0.1", "seed/history")
    session.commit()
    if statement_skipped:
        log_extra(log, "history application waits for statement", number=app.number)
    return app.id


def _bank_and_client_actions(factory: sessionmaker, rng: random.Random, ids: list[uuid.UUID], password: str) -> None:
    with factory() as session:
        staff = {u.bank_role: u for u in session.execute(select(User).where(User.kind == "bank")).scalars()}
        for app_id in ids:
            app = session.get(Application, app_id)
            try:
                if app.status == "manual_review" and rng.random() < 0.6:
                    _analyst_decision(session, rng, app, staff)
                elif app.status == "committee_review" and rng.random() < 0.5:
                    bank.decide(session, staff["risk_manager"], app, BankDecisionIn(action="approve", comment="Решение комитета"))
                session.commit()
            except AppError as e:
                session.rollback()
                log_extra(log, "history bank action skipped", number=app.number, reason=str(e))
    drain(factory, "seed")
    with factory() as session:
        for app_id in ids:
            app = session.get(Application, app_id)
            m = session.execute(select(CompanyMember).where(CompanyMember.company_id == app.company_id)).scalars().first()
            user = session.get(User, m.user_id)
            try:
                if app.status == "offer_issued":
                    r = rng.random()
                    if r < 0.7:
                        svc.accept_offer(session, user, app, m)
                        svc.sign_contract(session, user, app, m, password, "10.0.0.1", "seed/history")
                    elif r < 0.8:
                        svc.decline_offer(session, user, app, m, "Нашли другое финансирование")
                session.commit()
            except AppError as e:
                session.rollback()
                log_extra(log, "history client action skipped", number=app.number, reason=str(e))


def _analyst_decision(session: Session, rng: random.Random, app: Application, staff: dict) -> None:
    rec = bank.latest_recommendation(session, app.id)
    level = app.review_level or "analyst"
    who = {"analyst": staff["analyst"], "senior_analyst": staff["senior_analyst"]}.get(level)
    if who is None:  # нужен комитет
        bank.decide(session, staff["analyst"], app, BankDecisionIn(action="escalate", comment="Сумма выше полномочий"))
        return
    bank.assign(session, who, app)
    if rec and rec.outcome in ("approve", "counter_offer") and rng.random() < 0.85:
        bank.decide(session, who, app, BankDecisionIn(action="approve", comment="Данные подтверждены, риски приемлемы"))
    elif rec and rec.outcome == "decline":
        bank.decide(session, who, app, BankDecisionIn(action="decline", comment="Согласен с рекомендацией движка"))
    else:
        bank.decide(session, who, app, BankDecisionIn(action="decline", reason_codes=["SCORE_GRADE"],
                                                      comment="Совокупный риск выше допустимого после проверки данных"))


def _spread_in_time(factory: sessionmaker, rng: random.Random, ids: list[uuid.UUID]) -> None:
    now = utcnow()
    with factory() as session:
        for app_id in ids:
            app = session.get(Application, app_id)
            if app.submitted_at is None:
                continue
            if app.status in ("manual_review", "committee_review"):
                target = now - timedelta(hours=rng.uniform(0.5, 14))
            elif app.status in ("info_requested", "offer_issued", "offer_accepted"):
                target = now - timedelta(hours=rng.uniform(10, 120))
            else:
                target = now - timedelta(days=rng.uniform(1, 30), hours=rng.uniform(0, 10))
            delta = (target - app.submitted_at).total_seconds()
            manual_point = session.execute(text(
                "SELECT min(created_at) FROM application_events WHERE application_id = :id "
                "AND transition IN ('analyst_offer','analyst_decline','escalate','committee_offer','committee_decline')"),
                {"id": app_id}).scalar()
            _shift(session, app_id, delta)
            # автоматическая обработка в истории шла без пауз — восстанавливаем реалистичную длительность этапов
            _shift(session, app_id, rng.uniform(25, 90), after=target + timedelta(microseconds=1))
            if manual_point is not None:  # ручное решение — через несколько часов после поступления
                _shift(session, app_id, rng.uniform(1.5, 7.5) * 3600, after=manual_point + timedelta(seconds=delta - 0.001))
            session.commit()
