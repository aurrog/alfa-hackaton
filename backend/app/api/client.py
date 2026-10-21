"""API кабинета клиента: компании, подбор продукта, заявка, документы, подпись,
предложение, договор, кредиты, уведомления, лента, помощник."""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentUser, Meta, idempotent
from app.api.serializers import (
    application_summary,
    client_application,
    company_out,
    document_out,
    loan_out,
    notification_out,
    product_out,
)
from app.config import get_settings
from app.domain.calculator import loan_summary, schedule
from app.domain.products import PURPOSES, Need, eligibility, recommend
from app.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.integrations.client import http_client
from app.models import Application, CompanyMember, Loan, Notification, Product, Signature, Task
from app.schemas import (
    ApplicationCreate,
    ApplicationPatch,
    AssistantIn,
    CalculatorIn,
    CommentIn,
    CompanyConnectIn,
    FeedActionIn,
    FeedTopicsIn,
    PasswordIn,
    RecommendIn,
    SignSubmitIn,
    TaskAnswerIn,
)
from app.services import applications as svc
from app.services import assistant, companies, documents, feed_service
from app.services.access import client_application as load_app
from app.services.access import client_company
from app.services.audit import audit
from app.services.common import active_policy, company_profile, product_spec, today, utcnow
from app.services.offers import offer_schedule, render_contract

router = APIRouter(prefix="/api/v1", tags=["Кабинет клиента"])


def _app_out(db, app_id, user):
    app, m = load_app(db, user, app_id)
    return client_application(db, app, m)


# ================================================================== компании
@router.post("/companies", status_code=201, summary="Подключить компанию по ИНН (данные из ЕГРЮЛ/ЕГРИП)")
def connect_company(body: CompanyConnectIn, db: DB, user: CurrentUser, meta: Meta):
    if user.kind != "client":
        raise Forbidden("Раздел доступен только клиентам")
    c = companies.connect(db, user, body.inn, ip=meta[0])
    db.commit()
    m = db.execute(select(CompanyMember).where(CompanyMember.company_id == c.id,
                                               CompanyMember.user_id == user.id)).scalar_one()
    return company_out(c, m)


@router.get("/companies/{company_id}", summary="Карточка компании, предодобренные предложения, сводка")
def get_company(company_id: uuid.UUID, db: DB, user: CurrentUser):
    c, m = client_company(db, user, company_id)
    apps = db.execute(select(Application).where(Application.company_id == c.id)).scalars().all()
    loans = db.execute(select(Loan).where(Loan.company_id == c.id)).scalars().all()
    active = [a for a in apps if a.status not in ("issued", "declined", "client_declined", "cancelled", "expired")]
    return {**company_out(c, m), "preapproved": svc.preapproved_offers(db, c),
            "summary": {"applications": len(apps), "active_applications": len(active), "loans": len(loans),
                        "loans_amount": sum(float(lo.amount) for lo in loans),
                        "monthly_payments": sum(float(lo.monthly_payment) for lo in loans)}}


# ================================================================== продукты и подбор
@router.get("/products", summary="Каталог продуктов (с доступностью для компании)")
def list_products(db: DB, user: CurrentUser, company_id: uuid.UUID | None = None):
    policy = active_policy(db)
    products = db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order)).scalars().all()
    prof = None
    if company_id:
        c, _ = client_company(db, user, company_id)
        prof = company_profile(c)
    out = []
    for p in products:
        item = product_out(p, policy)
        item["blockers"] = eligibility(product_spec(p), prof) if prof else []
        item["eligible"] = not item["blockers"]
        out.append(item)
    return {"items": out, "purposes": [{"code": k, **v} for k, v in PURPOSES.items()], "key_rate": policy["key_rate"],
            "policy_version": policy.version}


@router.post("/products/recommend", summary="Подбор продукта под задачу клиента с объяснением")
def recommend_products(body: RecommendIn, db: DB, user: CurrentUser):
    c, _ = client_company(db, user, body.company_id)
    policy = active_policy(db)
    products = db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order)).scalars().all()
    pre = svc.preapproved_offers(db, c)
    it = svc.internal_turnover(svc.fetch_internal(db, c)) if c.is_bank_client else None
    need = Need(purpose=body.purpose, amount=body.amount, term_months=body.term_months, urgent=body.urgent,
                regular=body.regular, has_collateral=body.has_collateral)
    recs = recommend([product_spec(p) for p in products], need, company_profile(c, it["avg_monthly"] if it else None),
                     float(policy["key_rate"]), {o["product_code"]: o["max_amount"] for o in pre}, today())
    by_code = {p.code: p for p in products}
    for r in recs:
        p = by_code[r["code"]]
        r.update({"tagline": p.tagline, "kind": p.kind, "decision_time": p.decision_time, "features": p.features or [],
                  "min_term": p.min_term, "max_term": p.max_term, "min_amount": float(p.min_amount),
                  "max_amount": float(p.max_amount), "gov_program": p.gov_program})
    return {"items": recs, "need": body.model_dump(mode="json"), "preapproved": pre, "key_rate": policy["key_rate"]}


@router.post("/calculator", summary="Кредитный калькулятор: платёж, переплата, график")
def calculator(body: CalculatorIn, user: CurrentUser):
    if body.kind == "term_loan":
        s = loan_summary(body.amount, body.rate, body.term_months)
        rows = [r.as_dict() for r in schedule(body.amount, body.rate, body.term_months, today())]
    else:
        monthly = body.amount * body.rate / 1200
        s = {"monthly_payment": round(monthly, 2), "total_payment": round(monthly * body.term_months + body.amount, 2),
             "overpayment": round(monthly * body.term_months, 2),
             "effective_rate": round(((1 + body.rate / 1200) ** 12 - 1) * 100, 3)}
        rows = []
    return {**s, "schedule": rows}


# ================================================================== заявки
@router.get("/applications", summary="Заявки компаний пользователя")
def list_applications(db: DB, user: CurrentUser, company_id: uuid.UUID | None = None):
    if user.kind != "client":
        raise Forbidden("Раздел доступен только клиентам")
    members = {m.company_id: m for m in db.execute(select(CompanyMember).where(CompanyMember.user_id == user.id)).scalars()}
    ids = [company_id] if company_id else list(members)
    if company_id and company_id not in members:
        raise NotFound("Компания не найдена")
    apps = db.execute(select(Application).where(Application.company_id.in_(ids))
                      .order_by(Application.created_at.desc())).scalars().all() if ids else []
    return {"items": [application_summary(db, a, members[a.company_id]) for a in apps]}


@router.post("/applications", status_code=201, summary="Создать черновик заявки (с автозаполнением)")
def create_application(body: ApplicationCreate, db: DB, user: CurrentUser):
    app = svc.create_draft(db, user, body)
    db.commit()
    return _app_out(db, app.id, user)


@router.get("/applications/{app_id}", summary="Заявка: статус, маршрут, анкета, задачи, предложение")
def get_application(app_id: uuid.UUID, db: DB, user: CurrentUser):
    return _app_out(db, app_id, user)


@router.patch("/applications/{app_id}", summary="Изменить анкету черновика (автосохранение)")
def patch_application(app_id: uuid.UUID, body: ApplicationPatch, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.update_draft(db, user, app, m, body)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/documents", status_code=201, summary="Загрузить документ")
def upload_document(app_id: uuid.UUID, db: DB, user: CurrentUser,
                    doc_type: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    app, m = load_app(db, user, app_id)
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    doc = documents.upload(db, user, app, doc_type, file.filename or "file", file.content_type, data)
    db.commit()
    return {"document": document_out(doc), "application": client_application(db, app, m)}


@router.delete("/applications/{app_id}/documents/{doc_id}", summary="Удалить документ (до отправки)")
def delete_document(app_id: uuid.UUID, doc_id: uuid.UUID, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    doc = documents.get_document(db, doc_id)
    if doc.application_id != app.id:
        raise NotFound("Документ не найден")
    documents.delete(db, user, app, doc)
    db.commit()
    return client_application(db, app, m)


@router.get("/applications/{app_id}/documents/{doc_id}/file", summary="Скачать документ",
            response_class=FileResponse)
def download_document(app_id: uuid.UUID, doc_id: uuid.UUID, db: DB, user: CurrentUser):
    app, _ = load_app(db, user, app_id)
    doc = documents.get_document(db, doc_id)
    if doc.application_id != app.id:
        raise NotFound("Документ не найден")
    return FileResponse(documents.file_path(doc), media_type=doc.content_type, filename=doc.file_name)


@router.post("/applications/{app_id}/send-for-signature", summary="Передать заявку на подпись руководителю")
def send_for_signature(app_id: uuid.UUID, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.send_for_signature(db, user, app)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/return-to-draft", summary="Вернуть заявку на доработку")
def return_to_draft(app_id: uuid.UUID, body: CommentIn, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.return_to_draft(db, user, app, body.comment)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/submit", summary="Подписать (ПЭП) согласия и заявку, отправить в банк",
             description="Поддерживает заголовок `Idempotency-Key`: повтор не создаёт вторую подпись.")
def submit(app_id: uuid.UUID, body: SignSubmitIn, request: Request, db: DB, user: CurrentUser, meta: Meta):
    app, m = load_app(db, user, app_id)

    def act():
        svc.sign_and_submit(db, user, app, m, body.password, body.consent_bki, body.consent_pd, meta[0], meta[1])
        db.flush()
        return client_application(db, app, m)
    return idempotent(db, user, request, act)


@router.post("/applications/{app_id}/cancel", summary="Отозвать заявку")
def cancel(app_id: uuid.UUID, body: CommentIn, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.cancel(db, user, app, m, body.comment)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/tasks/{task_id}/answer", summary="Ответить на вопрос банка")
def answer_task(app_id: uuid.UUID, task_id: uuid.UUID, body: TaskAnswerIn, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    task = db.get(Task, task_id)
    if task is None or task.application_id != app.id:
        raise NotFound("Задача не найдена")
    if task.kind == "document":
        raise ValidationFailed("По этой задаче нужно загрузить документ")
    svc.answer_task(db, user, app, task, body.text)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/resume", summary="Вернуть заявку в работу после уточнений")
def resume(app_id: uuid.UUID, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.resume(db, user, app)
    db.commit()
    return client_application(db, app, m)


@router.post("/applications/{app_id}/offer/accept", summary="Принять кредитное предложение")
def accept_offer(app_id: uuid.UUID, request: Request, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)

    def act():
        svc.accept_offer(db, user, app, m)
        db.flush()
        return client_application(db, app, m)
    return idempotent(db, user, request, act)


@router.post("/applications/{app_id}/offer/decline", summary="Отказаться от предложения")
def decline_offer(app_id: uuid.UUID, body: CommentIn, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    svc.decline_offer(db, user, app, m, body.comment)
    db.commit()
    return client_application(db, app, m)


@router.get("/applications/{app_id}/contract", response_class=HTMLResponse,
            summary="Кредитный договор по принятому предложению (HTML)")
def contract(app_id: uuid.UUID, db: DB, user: CurrentUser):
    app, m = load_app(db, user, app_id)
    offer = svc.active_offer(db, app)
    if offer is None or offer.status != "accepted":
        raise Conflict("Договор формируется после принятия предложения")
    terms = svc.contract_terms(app, offer)
    sig = db.execute(select(Signature).where(Signature.application_id == app.id,
                                             Signature.document_kind == "loan_agreement")).scalars().first()
    if sig:
        terms["borrower"]["signatory"] = sig.signer_name
    rows = offer_schedule(offer, app.product.kind, (app.issued_at or utcnow()).date())
    return HTMLResponse(render_contract(terms, rows, sig))


@router.post("/applications/{app_id}/contract/sign", summary="Подписать кредитный договор (ПЭП)",
             description="Поддерживает заголовок `Idempotency-Key`.")
def sign_contract(app_id: uuid.UUID, body: PasswordIn, request: Request, db: DB, user: CurrentUser, meta: Meta):
    app, m = load_app(db, user, app_id)

    def act():
        svc.sign_contract(db, user, app, m, body.password, meta[0], meta[1])
        db.flush()
        return client_application(db, app, m)
    return idempotent(db, user, request, act)


# ================================================================== кредиты
@router.get("/loans", summary="Действующие кредиты компаний пользователя")
def list_loans(db: DB, user: CurrentUser, company_id: uuid.UUID | None = None):
    ids = [m.company_id for m in db.execute(select(CompanyMember).where(CompanyMember.user_id == user.id)).scalars()]
    if company_id:
        if company_id not in ids:
            raise NotFound("Компания не найдена")
        ids = [company_id]
    loans = db.execute(select(Loan).where(Loan.company_id.in_(ids)).order_by(Loan.issued_at.desc())).scalars().all() if ids else []
    products = {p.id: p for p in db.execute(select(Product)).scalars()}
    return {"items": [loan_out(lo, products[lo.product_id]) for lo in loans]}


# ================================================================== уведомления
@router.get("/notifications", summary="Уведомления в кабинете")
def notifications(db: DB, user: CurrentUser, limit: int = Query(30, ge=1, le=100)):
    rows = db.execute(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc()).limit(limit)).scalars().all()
    unread = db.execute(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))).scalar()
    return {"items": [notification_out(n) for n in rows], "unread": unread}


@router.post("/notifications/read-all", status_code=204, summary="Отметить все уведомления прочитанными")
def read_all(db: DB, user: CurrentUser):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
               .values(read_at=utcnow()))
    db.commit()


@router.post("/notifications/{notification_id}/read", status_code=204, summary="Отметить уведомление прочитанным")
def read_one(notification_id: uuid.UUID, db: DB, user: CurrentUser):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFound("Уведомление не найдено")
    n.read_at = n.read_at or utcnow()
    db.commit()


# ================================================================== лента
@router.get("/feed", summary="Персональная лента новостей и подсказок")
def feed(company_id: uuid.UUID, db: DB, user: CurrentUser):
    c, _ = client_company(db, user, company_id)
    return feed_service.build_feed(db, user, c)


@router.post("/feed/actions", status_code=204, summary="Реакция на карточку ленты (обучение интересов)")
def feed_action(body: FeedActionIn, db: DB, user: CurrentUser, company_id: uuid.UUID | None = None):
    if company_id:
        client_company(db, user, company_id)
    feed_service.record_action(db, user, body.news_id, body.action, company_id)
    db.commit()


@router.put("/feed/topics", status_code=204, summary="Выбрать интересующие темы")
def feed_topics(body: FeedTopicsIn, db: DB, user: CurrentUser):
    feed_service.set_topics(db, user, body.topics)
    db.commit()


# ================================================================== помощник
@router.post("/assistant", summary="Вопрос помощнику (база знаний + данные заявки)")
def ask(body: AssistantIn, db: DB, user: CurrentUser):
    app = None
    if body.application_id:
        app, _ = load_app(db, user, body.application_id)
    return assistant.answer(db, body.question, app)


# ================================================================== демо
@router.get("/demo/sample-statement/{company_id}", summary="Демо: синтетическая выписка 1С для компании",
            response_class=Response)
def sample_statement(company_id: uuid.UUID, db: DB, user: CurrentUser):
    if not get_settings().demo_mode:
        raise NotFound("Недоступно")
    c, _ = client_company(db, user, company_id)
    try:
        r = http_client().get(f"/samples/statements/{c.inn}", headers={"X-Mock-Latency": "0"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise Conflict("Симулятор недоступен — используйте файлы из test-data/statements", code="mocks_unavailable") from e
    audit(db, "demo.statement", user, entity_type="company", entity_id=str(c.id))
    db.commit()
    return Response(r.content, media_type="text/plain; charset=windows-1251",
                    headers={"Content-Disposition": f'attachment; filename="kl_to_1c_{c.inn}.txt"'})

