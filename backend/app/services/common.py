from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.decision.policy import Policy
from app.domain.products import CompanyProfile, ProductSpec
from app.errors import NotFound
from app.models import Company, CreditPolicy, Product, Sequence


def utcnow() -> datetime:
    return datetime.now(UTC)


def today() -> date:
    return utcnow().date()


def f(x: Decimal | float | int | None) -> float | None:
    return None if x is None else float(x)


def next_number(session: Session, name: str, prefix: str) -> str:
    seq = session.execute(select(Sequence).where(Sequence.name == name).with_for_update()).scalar_one_or_none()
    if seq is None:
        seq = Sequence(name=name, value=0)
        session.add(seq)
        session.flush()
    seq.value += 1
    session.flush()
    return f"{prefix}-{utcnow().year}-{seq.value:06d}"


def active_policy(session: Session) -> Policy:
    row = session.execute(select(CreditPolicy).where(CreditPolicy.is_active.is_(True))
                          .order_by(CreditPolicy.version.desc())).scalars().first()
    if row is None:
        return Policy.default()
    return Policy(row.version, row.config)


def product_spec(p: Product) -> ProductSpec:
    return ProductSpec(
        code=p.code, name=p.name, kind=p.kind, purposes=list(p.purposes or []), min_amount=float(p.min_amount),
        max_amount=float(p.max_amount), min_term=p.min_term, max_term=p.max_term, rate_mode=p.rate_mode,
        rate_spread=float(p.rate_spread), min_business_age_months=p.min_business_age_months,
        requires_bank_client=p.requires_bank_client, min_bank_client_months=p.min_bank_client_months,
        collateral_required_from=f(p.collateral_required_from), turnover_multiple=f(p.turnover_multiple),
        auto_decision=p.auto_decision, gov_program=p.gov_program, legal_forms=list(p.legal_forms or ["IP", "LE"]),
        decision_time=p.decision_time,
    )


def months_between(a: date | None, b: date) -> int:
    if a is None:
        return 0
    return max((b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0), 0)


def company_profile(c: Company, avg_turnover: float | None = None) -> CompanyProfile:
    return CompanyProfile(
        inn=c.inn, legal_form=c.legal_form, okved_code=c.okved_code, region_code=c.region_code,
        registration_date=c.registration_date, status=c.status, msp_category=c.msp_category,
        is_bank_client=c.is_bank_client, bank_client_months=months_between(c.bank_client_since, today()),
        avg_monthly_turnover=avg_turnover,
    )


def get_product(session: Session, code: str) -> Product:
    p = session.execute(select(Product).where(Product.code == code, Product.is_active.is_(True))).scalar_one_or_none()
    if p is None:
        raise NotFound(f"Продукт {code} не найден")
    return p
