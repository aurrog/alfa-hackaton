"""Вход, профиль, демо-учётные записи."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, Meta
from app.api.serializers import company_out, user_out
from app.config import get_settings
from app.errors import AppError, NotFound, Unauthorized
from app.models import CompanyMember, User
from app.schemas import LoginIn, TokenOut
from app.security import create_token, verify_password
from app.services.audit import audit
from app.services.common import utcnow

router = APIRouter(prefix="/api/v1/auth", tags=["Аутентификация"])

# Защита от подбора пароля на уровне приложения (дополнительно к лимиту в nginx):
# не более 10 неудачных попыток на e-mail за 5 минут.
_FAILS: dict[str, deque[float]] = defaultdict(deque)
_WINDOW, _MAX_FAILS = 300.0, 10


class TooManyAttempts(AppError):
    status, code, title = 429, "too_many_attempts", "Слишком много попыток"


def _throttled(email: str) -> bool:
    q = _FAILS[email]
    now = time.monotonic()
    while q and now - q[0] > _WINDOW:
        q.popleft()
    return len(q) >= _MAX_FAILS


@router.post("/login", response_model=TokenOut, summary="Вход по e-mail и паролю")
def login(body: LoginIn, db: DB, meta: Meta):
    email = body.email.strip().lower()
    if _throttled(email):
        raise TooManyAttempts("Слишком много неудачных попыток. Повторите через несколько минут.")
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        _FAILS[email].append(time.monotonic())
        audit(db, "auth.failed", None, actor_email=email, ip=meta[0], user_agent=meta[1])
        db.commit()
        raise Unauthorized("Неверный e-mail или пароль", code="bad_credentials")
    _FAILS.pop(email, None)
    token, exp = create_token(user.id, user.kind, user.bank_role)
    user.last_login_at = utcnow()
    audit(db, "auth.login", user, ip=meta[0], user_agent=meta[1])
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_at": exp.isoformat(), "user": user_out(user)}


@router.post("/logout", status_code=204, summary="Выход (запись в журнал аудита)")
def logout(db: DB, user: CurrentUser, meta: Meta):
    audit(db, "auth.logout", user, ip=meta[0], user_agent=meta[1])
    db.commit()


@router.get("/me", summary="Текущий пользователь и его компании")
def me(db: DB, user: CurrentUser):
    rows = db.execute(select(CompanyMember).where(CompanyMember.user_id == user.id)).scalars().all()
    return {"user": user_out(user),
            "companies": [company_out(m.company, m) for m in sorted(rows, key=lambda m: m.company.short_name)]}


ROLE_ORDER = {"analyst": 0, "senior_analyst": 1, "risk_manager": 2, "admin": 3}


@router.get("/demo-accounts", summary="Тестовые учётные записи (только в DEMO_MODE)")
def demo_accounts(db: DB):
    if not get_settings().demo_mode:
        raise NotFound("Недоступно")
    users = list(db.execute(select(User).where(User.demo_note.is_not(None), User.is_active.is_(True))).scalars().all())
    users.sort(key=lambda u: (u.kind != "client", ROLE_ORDER.get(u.bank_role or "", 9), u.demo_note or ""))
    out = []
    for u in users:
        company = None
        if u.kind == "client":
            m = db.execute(select(CompanyMember).where(CompanyMember.user_id == u.id)).scalars().first()
            company = m.company.short_name if m else None
        out.append({"email": u.email, "full_name": u.full_name, "kind": u.kind, "note": u.demo_note,
                    "company": company, "role_title": user_out(u)["role_title"]})
    return {"password": "Demo-2026", "accounts": out}
