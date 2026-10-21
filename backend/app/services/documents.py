"""Документы заявки: загрузка с проверкой типа и размера, хранение, разбор выписки,
связь с задачами-запросами, выдача файла по правам доступа.

Хранилище — каталог на томе (STORAGE_DIR). В промышленной среде тот же интерфейс
реализуется поверх S3-совместимого объектного хранилища с антивирусной проверкой.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.checklist import DOC_TYPES
from app.domain.statement_parser import StatementError, analyze
from app.domain.statuses import AppStatus
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import Application, Document, Task, User
from app.services import transitions
from app.services.common import utcnow

ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".txt", ".csv", ".xlsx", ".docx", ".xml"}
MAGIC = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"],
         ".xlsx": [b"PK"], ".docx": [b"PK"]}
UPLOAD_STATUSES = {AppStatus.DRAFT.value, AppStatus.PENDING_SIGNATURE.value, AppStatus.INFO_REQUESTED.value}


def _storage_root() -> Path:
    p = Path(get_settings().storage_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _safe_name(name: str) -> str:
    name = Path(name or "file").name
    name = re.sub(r"[^\w.\-() ]+", "_", name, flags=re.UNICODE).strip() or "file"
    return name[:120]


def upload(session: Session, user: User, app: Application, doc_type: str, file_name: str, content_type: str | None,
           data: bytes) -> Document:
    if app.status not in UPLOAD_STATUSES:
        raise Conflict("Документы можно загружать до отправки заявки или по запросу банка", code="upload_closed")
    if doc_type not in DOC_TYPES:
        raise ValidationFailed(f"Неизвестный тип документа: {doc_type}")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if len(data) == 0:
        raise ValidationFailed("Файл пустой")
    if len(data) > max_bytes:
        raise ValidationFailed(f"Файл больше {get_settings().max_upload_mb} МБ")
    safe = _safe_name(file_name)
    ext = Path(safe).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValidationFailed("Допустимые форматы: PDF, JPG, PNG, TXT, CSV, XLSX, DOCX, XML")
    if ext in MAGIC and not any(data.startswith(m) for m in MAGIC[ext]):
        raise ValidationFailed("Содержимое файла не соответствует расширению")

    parsed = None
    if doc_type == "bank_statement":
        if ext not in (".txt", ".csv"):
            raise ValidationFailed("Выписку загрузите в формате выгрузки 1С (.txt) или CSV — так обороты посчитаются автоматически")
        try:
            parsed = analyze(data, app.company.inn)
        except StatementError as e:
            raise ValidationFailed(f"Не удалось разобрать выписку: {e}", code="statement_invalid") from e

    doc_id = uuid.uuid4()
    key = f"{app.id}/{doc_id}__{safe}"
    path = _storage_root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    task = None
    if app.status == AppStatus.INFO_REQUESTED.value:
        task = session.execute(select(Task).where(Task.application_id == app.id, Task.status == "open",
                                                  Task.kind == "document", Task.doc_type == doc_type)).scalars().first()
    doc = Document(id=doc_id, application_id=app.id, doc_type=doc_type, file_name=safe,
                   content_type=content_type or "application/octet-stream", size_bytes=len(data),
                   sha256=hashlib.sha256(data).hexdigest(), storage_key=key, uploaded_by=user.id, parsed=parsed,
                   task_id=task.id if task else None)
    session.add(doc)
    if task is not None:
        task.status = "answered"
        task.answered_by = user.id
        task.answered_at = utcnow()

    if parsed is not None:
        app.statement = parsed
        if app.status in (AppStatus.DRAFT.value, AppStatus.PENDING_SIGNATURE.value):
            form = dict(app.form or {})
            fin = dict(form.get("financials") or {})
            prefill = dict(app.prefill or {})
            src = {"source": f"Выписка ({'1С' if parsed['format'] == '1c' else 'CSV'}), {parsed['months_covered']} мес.",
                   "at": utcnow().isoformat()}
            fin["monthly_revenue"] = round(parsed["avg_monthly_incoming"], -3)
            fin["revenue_last_year"] = round(parsed["annualized_revenue"], -3)
            prefill["financials.monthly_revenue"] = src
            prefill["financials.revenue_last_year"] = src
            if parsed.get("debt_payments_monthly"):
                fin["existing_loans_monthly_payment"] = parsed["debt_payments_monthly"]
                prefill["financials.existing_loans_monthly_payment"] = src
            form["financials"] = fin
            app.form = form
            app.prefill = prefill
    transitions.add_event(session, app, "document", f"Загружен документ: {DOC_TYPES[doc_type]['title']}",
                          actor_type="client", actor=user, details=safe,
                          payload={"document_id": str(doc_id), "parsed": bool(parsed)})
    return doc


def get_document(session: Session, doc_id: uuid.UUID) -> Document:
    d = session.get(Document, doc_id)
    if d is None:
        raise NotFound("Документ не найден")
    return d


def file_path(doc: Document) -> Path:
    p = (_storage_root() / doc.storage_key).resolve()
    if _storage_root().resolve() not in p.parents:
        raise NotFound("Документ не найден")
    if not p.exists():
        raise NotFound("Файл документа отсутствует в хранилище")
    return p


def delete(session: Session, user: User, app: Application, doc: Document) -> None:
    if app.status not in (AppStatus.DRAFT.value, AppStatus.PENDING_SIGNATURE.value):
        raise Conflict("Удалять документы можно только до отправки заявки")
    with contextlib.suppress(NotFound):
        file_path(doc).unlink(missing_ok=True)
    if doc.doc_type == "bank_statement":
        app.statement = None
    session.delete(doc)
    transitions.add_event(session, app, "document", f"Удалён документ: {doc.file_name}", actor_type="client", actor=user)
