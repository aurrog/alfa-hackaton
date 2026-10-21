"""Аутентификация: Argon2id для паролей, JWT (HS256) для доступа к API.

В промышленной эксплуатации вместо собственной выдачи токенов используется
корпоративный IdP (OIDC, например Keycloak) — API уже работает по Bearer-токену,
поэтому замена сводится к проверке подписи токена IdP.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import get_settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(user_id: uuid.UUID, kind: str, role: str | None) -> tuple[str, datetime]:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=s.jwt_ttl_minutes)
    payload = {"sub": str(user_id), "kind": kind, "role": role, "exp": exp, "iat": datetime.now(UTC),
               "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256"), exp


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
