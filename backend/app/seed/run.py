"""Наполнение тестовыми данными (идемпотентно): справочники, политика, лента,
учётные записи сценариев, история заявок через настоящий конвейер."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_factory
from app.domain.decision.policy import Policy
from app.integrations.client import http_client, set_http_client
from app.logging_setup import log_extra, setup_logging
from app.models import Application, Company, CompanyMember, CreditPolicy, NewsItem, Product, User
from app.security import hash_password
from app.seed.data import BANK_USERS, CLIENTS, DEMO_PASSWORD, PRODUCTS, STALE_CARD
from app.seed.news import NEWS
from app.services.common import today, utcnow
from app.services.companies import apply_registry, fetch_company

log = logging.getLogger("app.seed")


def fast_mocks_client() -> httpx.Client:
    """Клиент симулятора без искусственных задержек — для наполнения данными."""
    s = get_settings()
    return httpx.Client(base_url=s.integrations_base_url, timeout=httpx.Timeout(10.0, connect=3.0),
                        headers={"X-Mock-Latency": "0"})


def wait_for_mocks(timeout: float = 90.0) -> None:
    t0 = time.monotonic()
    while True:
        try:
            if http_client().get("/health", timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        if time.monotonic() - t0 > timeout:
            raise RuntimeError("Симулятор внешних систем недоступен")
        time.sleep(1.0)


def seed_reference(session: Session) -> None:
    for i, p in enumerate(PRODUCTS):
        row = session.execute(select(Product).where(Product.code == p["code"])).scalar_one_or_none()
        if row is None:
            row = Product(code=p["code"])
            session.add(row)
        row.name, row.tagline, row.description, row.kind = p["name"], p["tagline"], p["description"], p["kind"]
        row.purposes = p["purposes"]
        row.min_amount, row.max_amount = p["min_amount"], p["max_amount"]
        row.min_term, row.max_term = p["min_term"], p["max_term"]
        row.rate_mode = p.get("rate_mode", "spread")
        row.rate_spread = p.get("rate_spread", 5.0)
        row.min_business_age_months = p.get("min_business_age_months", 6)
        row.requires_bank_client = p.get("requires_bank_client", False)
        row.min_bank_client_months = p.get("min_bank_client_months", 0)
        row.collateral_required_from = p.get("collateral_required_from")
        row.turnover_multiple = p.get("turnover_multiple")
        row.auto_decision = p.get("auto_decision", True)
        row.gov_program = p.get("gov_program", False)
        row.legal_forms = p.get("legal_forms", ["IP", "LE"])
        row.features = p.get("features", [])
        row.decision_time = p.get("decision_time", "")
        row.sort_order = p.get("sort_order", (i + 1) * 10)
        row.is_active = True
    if session.execute(select(func.count()).select_from(CreditPolicy)).scalar() == 0:
        d = Policy.default()
        session.add(CreditPolicy(version=d.version, config=d.config, is_active=True,
                                 comment="Базовая версия кредитной политики"))
    for n in NEWS:
        row = session.get(NewsItem, n["id"]) or NewsItem(id=n["id"])
        row.title, row.summary, row.body, row.category = n["title"], n["summary"], n["body"], n["category"]
        row.topics, row.audience, row.strict = n.get("topics", []), n.get("audience", {}), n.get("strict", [])
        row.priority = n.get("priority", 0)
        if row.published_at is None:
            row.published_at = today() - timedelta(days=n.get("days_ago", 0))
        row.source, row.cta, row.is_active = n.get("source"), n.get("cta"), True
        session.add(row)
    session.flush()


def ensure_company(session: Session, inn: str) -> Company:
    c = session.execute(select(Company).where(Company.inn == inn)).scalar_one_or_none()
    if c is not None:
        return c
    egrul, msp, abs_data = fetch_company(session, inn)
    c = apply_registry(Company(), egrul, msp, abs_data)
    stale = STALE_CARD.get(inn)
    if stale:
        snap = dict(c.registry_snapshot or {})
        if "director_name" in stale:
            c.director_name = stale["director_name"]
        if "status" in stale:
            c.status = stale["status"]
        if "snapshot_director" in stale:
            snap["director"] = stale["snapshot_director"]
        if "snapshot_status" in stale:
            snap["status"] = stale["snapshot_status"]
        c.registry_snapshot = snap
        c.registry_checked_at = utcnow() - timedelta(days=stale.get("checked_days_ago", 90))
    session.add(c)
    session.flush()
    return c


def seed_users(session: Session) -> int:
    created = 0
    pwd = hash_password(DEMO_PASSWORD)
    for b in BANK_USERS:
        u = session.execute(select(User).where(User.email == b["email"])).scalar_one_or_none()
        if u is None:
            u = User(email=b["email"], password_hash=pwd, kind="bank")
            session.add(u)
            created += 1
        u.full_name, u.bank_role, u.position, u.demo_note = b["full_name"], b["role"], b["position"], b["note"]
        u.authority_limit = b["limit"]
    for cdef in CLIENTS:
        u = session.execute(select(User).where(User.email == cdef["email"])).scalar_one_or_none()
        if u is None:
            u = User(email=cdef["email"], password_hash=pwd, kind="client")
            session.add(u)
            created += 1
        u.full_name, u.phone, u.demo_note = cdef["full_name"], cdef.get("phone"), cdef["note"]
        u.personal_inn = cdef.get("personal_inn")
        u.birth_date = date.fromisoformat(cdef["birth_date"]) if cdef.get("birth_date") else None
        session.flush()
        for mdef in cdef["companies"]:
            c = ensure_company(session, mdef["inn"])
            m = session.execute(select(CompanyMember).where(CompanyMember.company_id == c.id,
                                                            CompanyMember.user_id == u.id)).scalar_one_or_none()
            if m is None:
                m = CompanyMember(company_id=c.id, user_id=u.id)
                session.add(m)
            m.role, m.can_sign, m.is_beneficiary, m.position = mdef["role"], mdef["can_sign"], mdef["beneficiary"], mdef["position"]
    session.flush()
    return created


def main(history: int | None = None) -> None:
    s = get_settings()
    setup_logging(s.log_level)
    previous = http_client()
    set_http_client(fast_mocks_client())
    try:
        wait_for_mocks()
        factory = session_factory()
        with factory() as session:
            seed_reference(session)
            created = seed_users(session)
            session.commit()
            has_history = session.execute(select(func.count()).select_from(Application)).scalar() > 0
        log_extra(log, "reference data and users seeded", users_created=created)
        n = s.seed_history if history is None else history
        if n > 0 and not has_history:
            from app.seed.history import generate
            generate(factory, n)
    finally:
        set_http_client(previous)


__all__ = ["main", "seed_reference", "seed_users", "ensure_company", "fast_mocks_client"]
