"""Журнал аудита безопасности: входы, просмотры досье сотрудниками банка,
решения, изменения политики, скачивание документов."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.logging_setup import request_id_var
from app.models import AuditLog, User


def audit(session: Session, action: str, actor: User | None = None, *, entity_type: str | None = None,
          entity_id: str | None = None, ip: str | None = None, user_agent: str | None = None,
          details: dict | None = None, actor_email: str | None = None) -> None:
    session.add(AuditLog(
        actor_id=actor.id if actor else None, actor_email=actor.email if actor else actor_email, action=action,
        entity_type=entity_type, entity_id=entity_id, ip=ip, user_agent=(user_agent or "")[:500] or None,
        request_id=request_id_var.get(), details=details,
    ))
