"""Контракты API (Pydantic). Описание полей попадает в OpenAPI (docs/05-api)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ------------------------------------------------------------------ аутентификация
class LoginIn(_In):
    email: str = Field(..., max_length=255, examples=["anna@kofe.test"])
    password: str = Field(..., min_length=1, max_length=128, examples=["Demo-2026"])


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: str
    user: dict[str, Any]


# ------------------------------------------------------------------ компании и подбор
class CompanyConnectIn(_In):
    inn: str = Field(..., pattern=r"^\d{10}(\d{2})?$", description="ИНН юрлица (10 цифр) или ИП (12 цифр)",
                     examples=["7707083893"])


Purpose = Literal["working_capital", "equipment", "cash_gap", "contract", "expansion", "any"]


class RecommendIn(_In):
    company_id: uuid.UUID
    purpose: Purpose = "any"
    amount: float = Field(1_000_000, gt=0, le=1_000_000_000)
    term_months: int = Field(12, ge=1, le=120)
    urgent: bool = False
    regular: bool = False
    has_collateral: bool = False


class CalculatorIn(_In):
    amount: float = Field(..., gt=0, le=1_000_000_000)
    rate: float = Field(..., ge=0, le=100)
    term_months: int = Field(..., ge=1, le=360)
    kind: Literal["term_loan", "overdraft", "credit_line"] = "term_loan"


# ------------------------------------------------------------------ заявка
class ApplicationCreate(_In):
    company_id: uuid.UUID
    product_code: str = Field(..., max_length=32, examples=["EXPRESS"])
    amount: float = Field(..., gt=0, le=1_000_000_000)
    term_months: int = Field(..., ge=1, le=120)
    purpose: Purpose = "any"
    preapproved: bool = False


class ContactPart(_In):
    name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=32, pattern=r"^[0-9+()\- ]{5,32}$")
    email: str | None = Field(None, max_length=255)
    position: str | None = Field(None, max_length=255)


class CompanyPart(_In):
    actual_address: str | None = Field(None, max_length=1000)
    employees: int | None = Field(None, ge=0, le=100_000)
    director_name: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=255)


class FinancialsPart(_In):
    revenue_last_year: float | None = Field(None, ge=0, le=100_000_000_000)
    monthly_revenue: float | None = Field(None, ge=0, le=10_000_000_000)
    net_profit_monthly: float | None = Field(None, ge=-10_000_000_000, le=10_000_000_000)
    existing_loans_monthly_payment: float | None = Field(None, ge=0, le=10_000_000_000)


class CollateralPart(_In):
    type: Literal["none", "real_estate", "equipment", "vehicle", "goods", "guarantee_fund"] | None = None
    value: float | None = Field(None, ge=0, le=100_000_000_000)
    description: str | None = Field(None, max_length=1000)


class GuarantorPart(_In):
    full_name: str | None = Field(None, max_length=255)
    inn: str | None = Field(None, pattern=r"^\d{12}$", description="ИНН физического лица (12 цифр)")
    birth_date: date | None = None
    share: float | None = Field(None, ge=0, le=100)


class ApplicationPatch(_In):
    """Частичное обновление черновика (автосохранение). Передаются только изменённые поля."""

    product_code: str | None = Field(None, max_length=32)
    amount: float | None = Field(None, gt=0, le=1_000_000_000)
    term_months: int | None = Field(None, ge=1, le=120)
    purpose: Purpose | None = None
    purpose_text: str | None = Field(None, max_length=2000)
    contact: ContactPart | None = None
    company: CompanyPart | None = None
    financials: FinancialsPart | None = None
    collateral: CollateralPart | None = None
    guarantor: GuarantorPart | None = None


class SignSubmitIn(_In):
    password: str = Field(..., min_length=1, max_length=128, description="Пароль для простой электронной подписи")
    consent_bki: bool = Field(..., description="Согласие на запрос кредитной истории (заёмщик и поручитель)")
    consent_pd: bool = Field(..., description="Согласие на обработку персональных данных")


class PasswordIn(_In):
    password: str = Field(..., min_length=1, max_length=128)


class CommentIn(_In):
    comment: str | None = Field(None, max_length=2000)


class TaskAnswerIn(_In):
    text: str = Field(..., min_length=1, max_length=4000)


# ------------------------------------------------------------------ лента и помощник
class FeedActionIn(_In):
    news_id: str = Field(..., max_length=128)
    action: Literal["view", "open", "like", "hide"]


class FeedTopicsIn(_In):
    topics: list[str] = Field(default_factory=list, max_length=30)


class AssistantIn(_In):
    question: str = Field(..., min_length=2, max_length=1000)
    application_id: uuid.UUID | None = None


# ------------------------------------------------------------------ банк
class InfoRequestItem(_In):
    kind: Literal["document", "question"] = "question"
    doc_type: str | None = Field(None, max_length=32)
    title: str | None = Field(None, max_length=512)
    description: str | None = Field(None, max_length=2000)


class BankDecisionIn(_In):
    action: Literal["approve", "decline", "request_info", "escalate", "rerun", "return"]
    amount: float | None = Field(None, gt=0, le=1_000_000_000)
    term_months: int | None = Field(None, ge=1, le=120)
    rate: float | None = Field(None, ge=0, le=100)
    conditions: list[str] | None = Field(None, max_length=20)
    reason_codes: list[str] | None = Field(None, max_length=10)
    comment: str | None = Field(None, max_length=4000)
    info_requests: list[dict[str, Any]] | None = Field(None, max_length=10)
    version: int | None = Field(None, description="Версия заявки, которую видел сотрудник (защита от параллельных изменений)")

    @field_validator("info_requests")
    @classmethod
    def _items(cls, v):
        if v is None:
            return v
        return [InfoRequestItem(**i).model_dump() for i in v]


class DocReviewIn(_In):
    status: Literal["accepted", "rejected"]
    comment: str | None = Field(None, max_length=2000)


class PolicyChangeIn(_In):
    changes: dict[str, float] = Field(..., description="Ключ параметра → новое значение (см. GET /bank/policy)")
    comment: str = Field(..., min_length=5, max_length=2000, description="Обоснование изменения политики")
