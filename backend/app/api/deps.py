"""Зависимости API: сессия БД, текущий пользователь, метаданные клиента, идемпотентность."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import Conflict, Unauthorized, ValidationFailed
from app.logging_setup import user_id_var
from app.models import IdempotencyRecord, User
from app.security import decode_token

DB = Annotated[Session, Depends(get_session)]


def current_user(db: DB, authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Войдите в кабинет")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Сессия истекла — войдите снова", code="token_expired") from None
    except jwt.PyJWTError:
        raise Unauthorized("Недействительный токен", code="invalid_token") from None
    try:
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        raise Unauthorized("Недействительный токен", code="invalid_token") from None
    if user is None or not user.is_active:
        raise Unauthorized("Пользователь не найден или заблокирован")
    user_id_var.set(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def client_meta(request: Request) -> tuple[str | None, str | None]:
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return ip, request.headers.get("user-agent")


Meta = Annotated[tuple[str | None, str | None], Depends(client_meta)]


def idempotent(db: Session, user: User, request: Request, action: Callable[[], Any], status_code: int = 200) -> Any:
    """Выполнить изменяющую операцию не более одного раза для заголовка Idempotency-Key.

    Повтор с тем же ключом (например, после обрыва связи при подписании) возвращает
    сохранённый ответ и не выполняет действие повторно. Ключ и результат фиксируются
    в той же транзакции, что и само действие.
    """
    key = request.headers.get("idempotency-key")
    if not key:
        body = jsonable_encoder(action())
        db.commit()
        return JSONResponse(body, status_code=status_code)
    if len(key) > 100:
        raise ValidationFailed("Idempotency-Key длиннее 100 символов")
    rec_key = f"{user.id}:{key}"
    rec = db.get(IdempotencyRecord, rec_key)
    if rec is not None:
        if rec.path != request.url.path or rec.method != request.method:
            raise ValidationFailed("Idempotency-Key уже использован для другого запроса", code="idempotency_key_reused")
        return JSONResponse(rec.response, status_code=rec.status_code, headers={"Idempotent-Replayed": "true"})
    body = jsonable_encoder(action())
    db.add(IdempotencyRecord(key=rec_key, user_id=user.id, method=request.method, path=request.url.path,
                             status_code=status_code, response=body))
    try:
        db.commit()
    except IntegrityError:  # параллельный запрос с тем же ключом успел первым
        db.rollback()
        raise Conflict("Запрос с этим Idempotency-Key уже выполняется", code="idempotency_in_progress") from None
    return JSONResponse(body, status_code=status_code)
