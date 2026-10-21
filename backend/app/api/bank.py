"""API рабочего места банка: очередь, досье, решения, документы, дашборд,
кредитная политика, журнал аудита, мониторинг конвейера."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentUser, Meta
from app.domain.decision.policy import EDITABLE, Policy, get_path
from app.errors import NotFound, ValidationFailed
from app.integrations.client import breaker_states
from app.models import Application, AuditLog, CreditPolicy, Job, User
from app.schemas import BankDecisionIn, DocReviewIn, PolicyChangeIn
from app.services import bank as svc
from app.services import documents
from app.services.access import DECISION_ROLES, POLICY_ROLES, require_bank
from app.services.audit import audit
from app.services.common import active_policy, utcnow
from app.services.memo import build_memo

router = APIRouter(prefix="/api/v1/bank", tags=["Рабочее место банка"])


def _app(db, app_id: uuid.UUID) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise NotFound("Заявка не найдена")
    return app


@router.get("/queue", summary="Очередь заявок с нормативами (SLA)")
def queue(db: DB, user: CurrentUser, status: str | None = Query(None, description="active | pipeline | all | <статус>"),
          assigned: str | None = Query(None, description="me | unassigned"), product: str | None = None,
          search: str | None = Query(None, max_length=100)):
    return svc.queue(db, user, status=status, assigned=assigned, product=product, search=search)


@router.get("/applications/{app_id}", summary="Досье заявки: источники, скоринг, рекомендация, журнал")
def dossier(app_id: uuid.UUID, db: DB, user: CurrentUser, meta: Meta):
    return svc.dossier(db, user, app_id, ip=meta[0], ua=meta[1])


@router.post("/applications/{app_id}/assign", summary="Взять заявку в работу")
def assign(app_id: uuid.UUID, db: DB, user: CurrentUser, meta: Meta):
    app = _app(db, app_id)
    svc.assign(db, user, app)
    audit(db, "bank.assign", user, entity_type="application", entity_id=str(app.id), ip=meta[0])
    db.commit()
    return svc.dossier(db, user, app_id)


@router.post("/applications/{app_id}/decision", summary="Решение по заявке в рамках полномочий",
             description="approve / decline / request_info / escalate / rerun (аналитик), approve / decline / return "
                         "(кредитный комитет). Поле `version` защищает от решения по устаревшим данным.")
def decision(app_id: uuid.UUID, body: BankDecisionIn, db: DB, user: CurrentUser, meta: Meta):
    app = _app(db, app_id)
    svc.decide(db, user, app, body)
    db.commit()
    return svc.dossier(db, user, app_id, ip=meta[0], ua=meta[1])


@router.get("/applications/{app_id}/memo", summary="Черновик кредитного заключения")
def memo(app_id: uuid.UUID, db: DB, user: CurrentUser):
    require_bank(user)
    d = svc.dossier(db, user, app_id)
    return build_memo(d)


@router.post("/documents/{doc_id}/review", summary="Принять или отклонить документ")
def review_document(doc_id: uuid.UUID, body: DocReviewIn, db: DB, user: CurrentUser):
    doc = documents.get_document(db, doc_id)
    svc.review_document(db, user, doc, body.status, body.comment)
    audit(db, "document.reviewed", user, entity_type="document", entity_id=str(doc.id), details={"status": body.status})
    db.commit()
    return {"id": doc.id, "status": doc.status, "review_comment": doc.review_comment}


@router.get("/documents/{doc_id}/file", summary="Скачать документ клиента", response_class=FileResponse)
def download(doc_id: uuid.UUID, db: DB, user: CurrentUser, meta: Meta):
    require_bank(user)
    doc = documents.get_document(db, doc_id)
    audit(db, "document.downloaded", user, entity_type="document", entity_id=str(doc.id), ip=meta[0], user_agent=meta[1])
    db.commit()
    return FileResponse(documents.file_path(doc), media_type=doc.content_type, filename=doc.file_name)


@router.get("/dashboard", summary="Дашборд кредитного процесса")
def dashboard(db: DB, user: CurrentUser, days: int = Query(30, ge=1, le=365)):
    return svc.dashboard(db, user, days)


# ------------------------------------------------------------------ кредитная политика
def _policy_view(db, policy: Policy) -> dict:
    rows = db.execute(select(CreditPolicy).order_by(CreditPolicy.version.desc()).limit(30)).scalars().all()
    names = {u.id: u.full_name for u in db.execute(select(User).where(User.kind == "bank")).scalars()}
    return {
        "version": policy.version, "config": policy.config,
        "editable": [{**e, "value": get_path(policy.config, e["key"])} for e in EDITABLE],
        "history": [{"version": r.version, "comment": r.comment, "is_active": r.is_active, "created_at": r.created_at,
                     "created_by": names.get(r.created_by)} for r in rows],
    }


@router.get("/policy", summary="Действующая кредитная политика и история версий")
def get_policy(db: DB, user: CurrentUser):
    require_bank(user)
    return _policy_view(db, active_policy(db))


@router.post("/policy", status_code=201, summary="Создать новую версию кредитной политики")
def change_policy(body: PolicyChangeIn, db: DB, user: CurrentUser, meta: Meta):
    require_bank(user, POLICY_ROLES)
    current = active_policy(db)
    try:
        cfg = current.with_changes(body.changes)
    except ValueError as e:
        raise ValidationFailed(str(e), code="policy_invalid") from e
    # блокировка от параллельного создания двух версий с одним номером
    last = db.execute(select(CreditPolicy).order_by(CreditPolicy.version.desc()).with_for_update().limit(1)).scalars().first()
    version = (last.version if last else 0) + 1
    db.execute(update(CreditPolicy).where(CreditPolicy.is_active.is_(True)).values(is_active=False))
    db.add(CreditPolicy(version=version, config=cfg, comment=body.comment, is_active=True, created_by=user.id))
    audit(db, "policy.changed", user, entity_type="credit_policy", entity_id=str(version), ip=meta[0],
          details={"from_version": current.version, "changes": body.changes, "comment": body.comment})
    db.commit()
    from app.services.applications import _preapproved_cache  # ставки предодобренных предложений — по новой версии
    _preapproved_cache.clear()
    return _policy_view(db, active_policy(db))


# ------------------------------------------------------------------ аудит и мониторинг
@router.get("/audit", summary="Журнал аудита")
def audit_log(db: DB, user: CurrentUser, action: str | None = None, limit: int = Query(100, ge=1, le=500)):
    require_bank(user, POLICY_ROLES)
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action.like(f"{action}%"))
    rows = db.execute(q).scalars().all()
    return {"items": [{"id": r.id, "action": r.action, "actor_email": r.actor_email, "entity_type": r.entity_type,
                       "entity_id": r.entity_id, "ip": r.ip, "request_id": r.request_id, "details": r.details,
                       "created_at": r.created_at} for r in rows]}


@router.get("/system", summary="Мониторинг конвейера: очередь задач, повторы, отказы")
def system(db: DB, user: CurrentUser):
    require_bank(user)
    by_status = dict(db.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    by_kind = [{"kind": k, "status": s, "count": n} for k, s, n in
               db.execute(select(Job.kind, Job.status, func.count()).group_by(Job.kind, Job.status)).all()]
    failed = db.execute(select(Job).where(Job.status == "failed").order_by(Job.id.desc()).limit(20)).scalars().all()
    retrying = db.execute(select(Job).where(Job.status == "queued", Job.attempts > 0).order_by(Job.id.desc()).limit(20)).scalars().all()
    oldest = db.execute(select(func.min(Job.run_after)).where(Job.status == "queued")).scalar()

    def job(j: Job) -> dict:
        return {"id": j.id, "kind": j.kind, "application_id": j.application_id, "status": j.status,
                "attempts": j.attempts, "max_attempts": j.max_attempts, "last_error": (j.last_error or "")[:300],
                "run_after": j.run_after, "finished_at": j.finished_at}
    return {"jobs_by_status": by_status, "jobs_by_kind": by_kind, "failed": [job(j) for j in failed],
            "retrying": [job(j) for j in retrying],
            "queue_lag_sec": max((utcnow() - oldest).total_seconds(), 0) if oldest else 0,
            "api_circuit_breakers": breaker_states()}


@router.post("/jobs/{job_id}/retry", summary="Повторить задачу из «мёртвых писем»")
def retry_job(job_id: int, db: DB, user: CurrentUser):
    require_bank(user, POLICY_ROLES | DECISION_ROLES)
    j = db.get(Job, job_id)
    if j is None or j.status != "failed":
        raise NotFound("Задача не найдена среди неуспешных")
    j.status, j.attempts, j.run_after, j.last_error = "queued", 0, utcnow(), "manual retry"
    audit(db, "job.retried", user, entity_type="job", entity_id=str(j.id))
    db.commit()
    return {"id": j.id, "status": j.status}
