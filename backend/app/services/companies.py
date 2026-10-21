"""Подключение компании к кабинету по ИНН (карточка создаётся из ЕГРЮЛ/ЕГРИП)."""

from __future__ import annotations

import contextlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.validators import is_valid_inn
from app.errors import Conflict, NotFound, ValidationFailed
from app.integrations.client import IntegrationClient, IntegrationError, NotFoundInSource, Sources
from app.models import Company, CompanyMember, User
from app.services.audit import audit
from app.services.common import utcnow


def apply_registry(c: Company, egrul: dict, msp: dict | None, abs_data: dict | None) -> Company:
    c.inn = egrul["inn"]
    c.ogrn = egrul.get("ogrn")
    c.kpp = egrul.get("kpp")
    c.legal_form = "IP" if egrul.get("type") == "IP" else "LE"
    c.name = egrul.get("full_name") or egrul.get("short_name")
    c.short_name = egrul.get("short_name") or c.name
    c.registration_date = date.fromisoformat(egrul["registration_date"]) if egrul.get("registration_date") else None
    addr = egrul.get("address") or {}
    c.address = addr.get("full")
    c.region_code = addr.get("region_code")
    okv = egrul.get("okved_main") or {}
    c.okved_code, c.okved_name = okv.get("code"), okv.get("name")
    c.status = (egrul.get("status") or {}).get("code", "active")
    c.director_name = (egrul.get("director") or {}).get("full_name")
    c.registry_snapshot = egrul
    c.registry_checked_at = utcnow()
    if msp is not None:
        c.msp_category = msp.get("category") if msp.get("in_registry") else None
    if abs_data:
        c.is_bank_client = True
        c.bank_client_since = date.fromisoformat(abs_data["client_since"]) if abs_data.get("client_since") else None
        c.settlement_account = abs_data.get("settlement_account")
    else:
        c.is_bank_client = False
    return c


def fetch_company(session: Session, inn: str) -> tuple[dict, dict | None, dict | None]:
    src = Sources(IntegrationClient(session, None, retries=1))
    try:
        egrul = src.egrul(inn)
    except NotFoundInSource:
        raise NotFound("Компания с таким ИНН не найдена в ЕГРЮЛ/ЕГРИП") from None
    except IntegrationError as e:
        raise Conflict(f"ЕГРЮЛ временно недоступен, попробуйте позже ({e.kind})", code="registry_unavailable") from e
    msp = abs_data = None
    with contextlib.suppress(IntegrationError):
        msp = src.msp(inn)
    with contextlib.suppress(IntegrationError):
        abs_data = src.abs_client(inn)
    return egrul, msp, abs_data


def connect(session: Session, user: User, inn: str, ip: str | None = None) -> Company:
    inn = inn.strip()
    if not is_valid_inn(inn):
        raise ValidationFailed("ИНН некорректен: проверьте количество цифр и контрольные разряды", code="invalid_inn")
    existing = session.execute(select(Company).where(Company.inn == inn)).scalar_one_or_none()
    if existing is not None:
        member = session.execute(select(CompanyMember).where(CompanyMember.company_id == existing.id,
                                                             CompanyMember.user_id == user.id)).scalar_one_or_none()
        if member:
            return existing
        raise Conflict("Компания уже подключена к кабинету другим пользователем — попросите руководителя добавить вас",
                       code="company_taken")
    egrul, msp, abs_data = fetch_company(session, inn)
    c = apply_registry(Company(), egrul, msp, abs_data)
    session.add(c)
    session.flush()
    # В прототипе полномочия подтверждаются автоматически; в промышленной версии —
    # через ЕСИА (руководитель из ЕГРЮЛ) или машиночитаемую доверенность (МЧД).
    session.add(CompanyMember(company_id=c.id, user_id=user.id, role="director", can_sign=True, is_beneficiary=True,
                              position=(egrul.get("director") or {}).get("position") or "Руководитель"))
    audit(session, "company.connected", user, entity_type="company", entity_id=str(c.id), ip=ip, details={"inn": inn})
    return c
