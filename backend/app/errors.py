"""Доменные ошибки и единый формат ответов об ошибках (RFC 7807 problem+json)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from app.domain.state_machine import TransitionError
from app.logging_setup import request_id_var

log = logging.getLogger("app.errors")


class AppError(Exception):
    status = 400
    code = "bad_request"
    title = "Некорректный запрос"

    def __init__(self, detail: str | None = None, *, code: str | None = None, extra: dict | None = None):
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        if code:
            self.code = code
        self.extra = extra or {}


class NotFound(AppError):
    status, code, title = 404, "not_found", "Не найдено"


class Forbidden(AppError):
    status, code, title = 403, "forbidden", "Доступ запрещён"


class Unauthorized(AppError):
    status, code, title = 401, "unauthorized", "Требуется вход"


class Conflict(AppError):
    status, code, title = 409, "conflict", "Конфликт состояния"


class ValidationFailed(AppError):
    status, code, title = 422, "validation_failed", "Ошибка проверки данных"


def _problem(status: int, code: str, title: str, detail: str, extra: dict | None = None) -> JSONResponse:
    body = {"type": f"https://errors.credit-cabinet.local/{code}", "title": title, "status": status,
            "detail": detail, "code": code, "request_id": request_id_var.get()}
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _problem(exc.status, exc.code, exc.title, exc.detail, exc.extra)

    @app.exception_handler(TransitionError)
    async def _transition(_: Request, exc: TransitionError):
        status = 403 if exc.code == "forbidden_transition" else 409
        return _problem(status, exc.code, "Действие недоступно", str(exc))

    @app.exception_handler(StaleDataError)
    async def _stale(_: Request, exc: StaleDataError):
        return _problem(409, "stale_version", "Заявка изменилась",
                        "Заявка была изменена параллельно. Обновите страницу и повторите действие.")

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg")} for e in exc.errors()]
        return _problem(422, "validation_failed", "Ошибка проверки данных", "Проверьте заполнение полей", {"errors": errors})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return _problem(500, "internal_error", "Внутренняя ошибка", "Что-то пошло не так. Мы уже разбираемся.")
