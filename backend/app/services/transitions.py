"""Единая точка изменения статуса заявки.

Проверяет переход по машине состояний, обновляет статус и SLA, пишет событие
в журнал заявки, создаёт уведомления в кабинете (почта/SMS не используются —
весь сценарий внутри продукта) и метрики. Конкурентные изменения отсекаются
оптимистической блокировкой (version_id_col) → HTTP 409.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.state_machine import Actor, resolve
from app.domain.statuses import STATUS_META, AppStatus
from app.metrics import TRANSITIONS
from app.models import Application, ApplicationEvent, CompanyMember, Notification, User
from app.services.common import utcnow

ACTOR_TYPE = {
    Actor.CLIENT: "client", Actor.CLIENT_SIGNER: "client", Actor.SYSTEM: "system",
    Actor.ANALYST: "bank", Actor.COMMITTEE: "bank",
}

# Уведомления клиенту при входе в статус: (вид, заголовок, только подписантам)
CLIENT_NOTIFY: dict[AppStatus, tuple[str, str, bool]] = {
    AppStatus.PENDING_SIGNATURE: ("action", "Заявка {n} ждёт вашей подписи", True),
    AppStatus.SUBMITTED: ("info", "Заявка {n} отправлена в банк", False),
    AppStatus.INFO_REQUESTED: ("action", "По заявке {n} нужны уточнения", False),
    AppStatus.MANUAL_REVIEW: ("info", "Заявку {n} рассматривает специалист", False),
    AppStatus.COMMITTEE_REVIEW: ("info", "Заявка {n} вынесена на кредитный комитет", False),
    AppStatus.OFFER_ISSUED: ("action", "Предложение по заявке {n} готово", False),
    AppStatus.OFFER_ACCEPTED: ("action", "Подпишите кредитный договор по заявке {n}", True),
    AppStatus.ISSUED: ("success", "Кредит по заявке {n} выдан", False),
    AppStatus.DECLINED: ("warning", "Решение по заявке {n}", False),
    AppStatus.EXPIRED: ("warning", "Срок по заявке {n} истёк", False),
}


def add_event(session: Session, app: Application, kind: str, title: str, *, details: str | None = None,
              actor_type: str = "system", actor: User | None = None, visibility: str = "all",
              payload: dict | None = None, transition: str | None = None, from_status: str | None = None,
              to_status: str | None = None) -> ApplicationEvent:
    ev = ApplicationEvent(
        application_id=app.id, kind=kind, title=title, details=details, actor_type=actor_type,
        actor_id=actor.id if actor else None, actor_name=actor.full_name if actor else None,
        visibility=visibility, payload=payload, transition=transition, from_status=from_status, to_status=to_status,
    )
    session.add(ev)
    return ev


def notify_company(session: Session, app: Application, kind: str, title: str, body: str | None = None,
                   signers_only: bool = False, exclude_user=None) -> None:
    q = select(CompanyMember).where(CompanyMember.company_id == app.company_id)
    for m in session.execute(q).scalars():
        if signers_only and not m.can_sign:
            continue
        if exclude_user is not None and m.user_id == exclude_user:
            continue
        session.add(Notification(user_id=m.user_id, application_id=app.id, kind=kind, title=title, body=body,
                                 link=f"/applications/{app.id}"))


def apply(session: Session, app: Application, name: str, actor: Actor, user: User | None = None, *,
          comment: str | None = None, payload: dict | None = None, notify: bool = True,
          notify_body: str | None = None) -> ApplicationEvent:
    t = resolve(name, app.status, actor)
    prev = app.status
    now = utcnow()
    app.status = t.target.value
    app.status_changed_at = now
    meta = STATUS_META[t.target]
    app.sla_due_at = now + timedelta(hours=meta.sla_hours) if meta.sla_hours else None
    if t.target in (AppStatus.OFFER_ISSUED, AppStatus.DECLINED) and app.decided_at is None:
        app.decided_at = now
    if t.target == AppStatus.ISSUED:
        app.issued_at = now
    ev = add_event(session, app, "status", t.title, details=comment, actor_type=ACTOR_TYPE[actor], actor=user,
                   payload=payload, transition=name, from_status=prev, to_status=t.target.value)
    TRANSITIONS.labels(name).inc()
    if notify and t.target in CLIENT_NOTIFY:
        kind, title, signers_only = CLIENT_NOTIFY[t.target]
        notify_company(session, app, kind, title.format(n=app.number), notify_body or meta.client_hint,
                       signers_only=signers_only,
                       exclude_user=user.id if user and actor in (Actor.CLIENT, Actor.CLIENT_SIGNER) else None)
    session.flush()
    return ev
