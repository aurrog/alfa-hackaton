"""Постановка задач в очередь конвейера (в той же транзакции, что и бизнес-изменение)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job
from app.services.common import utcnow


def enqueue(session: Session, kind: str, application_id: uuid.UUID | None = None, payload: dict | None = None, *,
            delay_sec: float = 0.0, dedup_key: str | None = None, priority: int = 100,
            max_attempts: int | None = None) -> Job | None:
    if dedup_key:
        existing = session.execute(select(Job).where(Job.dedup_key == dedup_key)).scalar_one_or_none()
        if existing is not None:
            return None
    job = Job(kind=kind, application_id=application_id, payload=payload or {}, priority=priority,
              max_attempts=max_attempts or get_settings().job_max_attempts,
              run_after=utcnow() + timedelta(seconds=delay_sec), dedup_key=dedup_key)
    session.add(job)
    return job
