"""Исполнитель очереди конвейера.

* Задача забирается `SELECT … FOR UPDATE SKIP LOCKED` — несколько воркеров
  работают параллельно без дублей (горизонтальное масштабирование).
* Повторы с экспоненциальной паузой; после исчерпания попыток задача
  помечается failed (dead letter) и видна в мониторинге.
* «Зависшие» задачи (воркер упал посреди обработки) возвращаются в очередь
  по истечении аренды (lease).
* Обслуживание сроков выполняется под advisory-lock — одним воркером за раз.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.config import get_settings
from app.logging_setup import job_var, log_extra
from app.metrics import JOB_LATENCY, JOBS
from app.models import Job
from app.services.common import utcnow
from app.services.pipeline import HANDLERS, RetryLater, expire_overdue

log = logging.getLogger("app.worker")


def _backoff(attempts: int) -> float:
    return min(1.5 * 2 ** (attempts - 1), 30.0)


def pick(session: Session, worker_id: str, ignore_schedule: bool = False) -> Job | None:
    q = select(Job).where(Job.status == "queued")
    if not ignore_schedule:
        q = q.where(Job.run_after <= utcnow())
    job = session.execute(q.order_by(Job.priority, Job.id).with_for_update(skip_locked=True).limit(1)).scalar_one_or_none()
    if job is None:
        session.rollback()
        return None
    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = utcnow()
    job.attempts += 1
    session.commit()
    return job


def _finish(factory: sessionmaker, job_id: int, **values) -> None:
    with factory() as s:
        s.execute(update(Job).where(Job.id == job_id).values(**values))
        s.commit()


def run_one(factory: sessionmaker, worker_id: str, ignore_schedule: bool = False) -> bool:
    with factory() as s:
        job = pick(s, worker_id, ignore_schedule)
    if job is None:
        return False
    token = job_var.set(f"{job.kind}#{job.id}")
    last = job.attempts >= job.max_attempts
    t0 = time.perf_counter()
    session = factory()
    try:
        handler = HANDLERS.get(job.kind)
        if handler is None:
            raise RuntimeError(f"unknown job kind {job.kind}")
        handler(session, job, last)
        session.commit()
        _finish(factory, job.id, status="done", finished_at=utcnow(), last_error=None)
        JOBS.labels(job.kind, "done").inc()
        log_extra(log, "job done", kind=job.kind, application_id=str(job.application_id), attempt=job.attempts)
    except RetryLater as e:
        session.commit()  # сохранить прогресс этапа и журнал вызовов источников
        if last:
            _finish(factory, job.id, status="failed", finished_at=utcnow(), last_error=str(e))
            JOBS.labels(job.kind, "failed").inc()
        else:
            delay = e.delay_sec or _backoff(job.attempts)
            _finish(factory, job.id, status="queued", run_after=utcnow() + timedelta(seconds=delay), last_error=str(e))
            JOBS.labels(job.kind, "retry").inc()
            log_extra(log, "job retry scheduled", level=logging.WARNING, kind=job.kind, delay=delay, reason=str(e))
    except StaleDataError as e:
        session.rollback()
        _finish(factory, job.id, status="queued", run_after=utcnow() + timedelta(seconds=0.5), last_error="stale: " + str(e))
        JOBS.labels(job.kind, "conflict").inc()
    except Exception as e:  # noqa: BLE001
        session.rollback()
        log.exception("job failed: %s", job.kind)
        if last:
            _finish(factory, job.id, status="failed", finished_at=utcnow(), last_error=repr(e)[:2000])
            JOBS.labels(job.kind, "failed").inc()
        else:
            _finish(factory, job.id, status="queued", run_after=utcnow() + timedelta(seconds=_backoff(job.attempts)),
                    last_error=repr(e)[:2000])
            JOBS.labels(job.kind, "retry").inc()
    finally:
        session.close()
        JOB_LATENCY.labels(job.kind).observe(time.perf_counter() - t0)
        job_var.reset(token)
    return True


def maintenance(factory: sessionmaker) -> None:
    s = get_settings()
    with factory() as session:
        got = session.execute(text("SELECT pg_try_advisory_xact_lock(7340021)")).scalar()
        if not got:
            return
        lease_limit = utcnow() - timedelta(seconds=s.job_lease_sec)
        session.execute(update(Job).where(Job.status == "running", Job.locked_at < lease_limit)
                        .values(status="queued", locked_by=None, last_error="lease expired, requeued"))
        try:
            n = expire_overdue(session)
            session.commit()
            if n:
                log_extra(log, "expired applications", count=n)
        except StaleDataError:
            session.rollback()


def drain(factory: sessionmaker, worker_id: str = "inline", max_jobs: int = 500) -> int:
    """Выполнить все задачи синхронно (тесты, генерация истории), игнорируя отложенный запуск."""
    n = 0
    while n < max_jobs and run_one(factory, worker_id, ignore_schedule=True):
        n += 1
    return n


def loop(factory: sessionmaker, stop) -> None:
    s = get_settings()
    last_maint = 0.0
    log_extra(log, "worker started", worker_id=s.worker_id)
    while not stop():
        try:
            busy = run_one(factory, s.worker_id)
            if time.monotonic() - last_maint > 30:
                maintenance(factory)
                last_maint = time.monotonic()
        except OperationalError:
            log.exception("database unavailable, backing off")
            busy = False
            time.sleep(2)
        if not busy:
            time.sleep(s.worker_poll_interval_sec)
    log_extra(log, "worker stopped", worker_id=s.worker_id)
