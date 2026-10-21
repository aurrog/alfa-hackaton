"""Модель данных (PostgreSQL). Описание таблиц и связей — docs/06-data-model."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)


# --------------------------------------------------------------------------- пользователи и компании
class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))  # client | bank
    bank_role: Mapped[str | None] = mapped_column(String(32))  # analyst | senior_analyst | risk_manager | admin
    position: Mapped[str | None] = mapped_column(String(255))
    authority_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    personal_inn: Mapped[str | None] = mapped_column(String(12))
    birth_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    demo_note: Mapped[str | None] = mapped_column(Text)

    memberships: Mapped[list[CompanyMember]] = relationship(back_populates="user")


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    inn: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    ogrn: Mapped[str | None] = mapped_column(String(15))
    kpp: Mapped[str | None] = mapped_column(String(9))
    legal_form: Mapped[str] = mapped_column(String(8))  # IP | LE
    name: Mapped[str] = mapped_column(String(512))
    short_name: Mapped[str] = mapped_column(String(255))
    registration_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(Text)
    region_code: Mapped[str | None] = mapped_column(String(4))
    okved_code: Mapped[str | None] = mapped_column(String(16))
    okved_name: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="active")
    director_name: Mapped[str | None] = mapped_column(String(255))
    msp_category: Mapped[str | None] = mapped_column(String(16))
    is_bank_client: Mapped[bool] = mapped_column(Boolean, default=False)
    bank_client_since: Mapped[date | None] = mapped_column(Date)
    settlement_account: Mapped[str | None] = mapped_column(String(20))
    registry_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    registry_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    members: Mapped[list[CompanyMember]] = relationship(back_populates="company")


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (UniqueConstraint("company_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))  # owner | director | accountant | employee
    can_sign: Mapped[bool] = mapped_column(Boolean, default=False)
    is_beneficiary: Mapped[bool] = mapped_column(Boolean, default=False)  # собственник → поручитель
    position: Mapped[str | None] = mapped_column(String(255))

    company: Mapped[Company] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


# --------------------------------------------------------------------------- продукты и политика
class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    tagline: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(32))
    purposes: Mapped[list[Any]] = mapped_column(JSONB)
    min_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    min_term: Mapped[int] = mapped_column(Integer)
    max_term: Mapped[int] = mapped_column(Integer)
    rate_mode: Mapped[str] = mapped_column(String(16), default="spread")
    rate_spread: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("5"))
    min_business_age_months: Mapped[int] = mapped_column(Integer, default=6)
    requires_bank_client: Mapped[bool] = mapped_column(Boolean, default=False)
    min_bank_client_months: Mapped[int] = mapped_column(Integer, default=0)
    collateral_required_from: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    turnover_multiple: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    auto_decision: Mapped[bool] = mapped_column(Boolean, default=True)
    gov_program: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_forms: Mapped[list[Any]] = mapped_column(JSONB, default=lambda: ["IP", "LE"])
    features: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    decision_time: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreditPolicy(Base):
    __tablename__ = "credit_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- заявки
class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (Index("ix_applications_status_sla", "status", "sla_due_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(32), default="any")
    purpose_text: Mapped[str | None] = mapped_column(Text)
    form: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # анкета (контакты, финансы, залог…)
    prefill: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # что и откуда заполнено автоматически
    enrichment: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # нормализованные внешние данные
    statement: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # аналитика выписки
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    review_level: Mapped[str | None] = mapped_column(String(32))  # auto | analyst | senior_analyst | committee
    sticky_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_reasons: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    risk_grade: Mapped[str | None] = mapped_column(String(2))
    score: Mapped[int | None] = mapped_column(Integer)
    pd: Mapped[float | None] = mapped_column(Float)
    decision_outcome: Mapped[str | None] = mapped_column(String(32))
    source_channel: Mapped[str] = mapped_column(String(32), default="cabinet")
    preapproved: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version}

    company: Mapped[Company] = relationship(lazy="joined")
    product: Mapped[Product] = relationship(lazy="joined")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # status | note | check | integration | document | task | signature | decision
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str | None] = mapped_column(String(32))
    transition: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    details: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(16))  # client | bank | system
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str | None] = mapped_column(String(255))
    visibility: Mapped[str] = mapped_column(String(16), default="all")  # all | bank
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))
    doc_type: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="uploaded")  # uploaded | accepted | rejected
    review_comment: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    """Запрос информации у клиента (документ или вопрос)."""

    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # document | question
    doc_type: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | answered | closed | cancelled
    created_by_type: Mapped[str] = mapped_column(String(16))  # system | bank
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    answer_text: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationCall(Base):
    __tablename__ = "integration_calls"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))  # ok | error | timeout | circuit_open | rejected | not_found
    http_status: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    request: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CheckResult(Base):
    __tablename__ = "check_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    stage: Mapped[str] = mapped_column(String(16))  # validation | policy
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    result: Mapped[str] = mapped_column(String(16))
    effect: Mapped[str | None] = mapped_column(String(16))
    details: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScoringResult(Base):
    __tablename__ = "scoring_results"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    model_id: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    score: Mapped[int] = mapped_column(Integer)
    pd: Mapped[float] = mapped_column(Float)
    grade: Mapped[str] = mapped_column(String(2))
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    factors: Mapped[list[Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(16))  # recommendation | final
    outcome: Mapped[str] = mapped_column(String(32))  # approve | counter_offer | decline
    level: Mapped[str] = mapped_column(String(32))  # auto | analyst | senior_analyst | committee
    policy_version: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(String(32))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int | None] = mapped_column(Integer)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    conditions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    reason_codes: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    comment: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_by_name: Mapped[str | None] = mapped_column(String(255))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # полная рекомендация движка
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decisions.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_payment: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    overpayment: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    conditions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    changes: Mapped[list[Any]] = mapped_column(JSONB, default=list)  # чем отличается от запроса
    is_counter: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | accepted | declined | expired | superseded
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signature(Base):
    __tablename__ = "signatures"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    document_kind: Mapped[str] = mapped_column(String(32))
    document_title: Mapped[str] = mapped_column(String(512))
    document_hash: Mapped[str] = mapped_column(String(64))
    signer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    signer_name: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(16), default="pep")
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Loan(Base):
    __tablename__ = "loans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    contract_number: Mapped[str] = mapped_column(String(64))
    loan_account: Mapped[str] = mapped_column(String(20))
    settlement_account: Mapped[str | None] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    schedule: Mapped[list[Any]] = mapped_column(JSONB)
    abs_reference: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- инфраструктура
class Job(Base):
    """Очередь задач конвейера в PostgreSQL (FOR UPDATE SKIP LOCKED).

    Запись задачи создаётся в той же транзакции, что и смена статуса заявки
    (transactional outbox) — задача не потеряется и не выполнится «раньше времени».
    """

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_pick", "status", "run_after", "priority"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | running | done | failed
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_by: Mapped[str | None] = mapped_column(String(128))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    dedup_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # info | action | success | warning
    title: Mapped[str] = mapped_column(String(512))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    topics: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    strict: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[date] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(512))
    cta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FeedInteraction(Base):
    __tablename__ = "feed_interactions"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    news_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))  # view | open | like | hide
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FeedPreference(Base):
    __tablename__ = "feed_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    selected_topics: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    topic_weights: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sequence(Base):
    """Счётчики для человекочитаемых номеров (КЗ-2026-000123)."""

    __tablename__ = "sequences"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0)
