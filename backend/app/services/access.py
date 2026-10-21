"""Объектная авторизация: клиент видит только заявки своих компаний,
действия с правом подписи — только у подписантов; сотрудники банка — по ролям."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Forbidden, NotFound
from app.models import Application, Company, CompanyMember, User

ROLE_TITLES = {
    "owner": "Собственник", "director": "Руководитель", "accountant": "Бухгалтер", "employee": "Сотрудник",
    "analyst": "Кредитный аналитик", "senior_analyst": "Старший кредитный аналитик",
    "risk_manager": "Риск-менеджер (кредитный комитет)", "admin": "Администратор кредитного процесса",
}

BANK_ROLES = {"analyst", "senior_analyst", "risk_manager", "admin"}
DECISION_ROLES = {"analyst", "senior_analyst", "risk_manager"}
COMMITTEE_ROLES = {"risk_manager"}
POLICY_ROLES = {"admin", "risk_manager"}


def membership(session: Session, user: User, company_id: uuid.UUID) -> CompanyMember:
    m = session.execute(select(CompanyMember).where(CompanyMember.company_id == company_id,
                                                    CompanyMember.user_id == user.id)).scalar_one_or_none()
    if m is None:
        # не раскрываем существование чужой компании
        raise NotFound("Компания не найдена")
    return m


def client_company(session: Session, user: User, company_id: uuid.UUID) -> tuple[Company, CompanyMember]:
    if user.kind != "client":
        raise Forbidden("Раздел доступен только клиентам")
    m = membership(session, user, company_id)
    return session.get(Company, company_id), m


def client_application(session: Session, user: User, app_id: uuid.UUID) -> tuple[Application, CompanyMember]:
    if user.kind != "client":
        raise Forbidden("Раздел доступен только клиентам")
    app = session.get(Application, app_id)
    if app is None:
        raise NotFound("Заявка не найдена")
    try:
        m = membership(session, user, app.company_id)
    except NotFound:
        raise NotFound("Заявка не найдена") from None
    return app, m


def require_signer(m: CompanyMember) -> None:
    if not m.can_sign:
        raise Forbidden("Действие доступно только руководителю или собственнику с правом подписи",
                        code="signer_required")


def require_bank(user: User, roles: set[str] | None = None) -> None:
    if user.kind != "bank" or user.bank_role not in BANK_ROLES:
        raise Forbidden("Раздел доступен только сотрудникам банка")
    if roles and user.bank_role not in roles:
        raise Forbidden("Недостаточно полномочий для этого действия")
