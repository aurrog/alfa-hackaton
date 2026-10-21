"""Помощник клиента: отвечает на вопросы о терминах, процессе и статусе своей заявки.

Факты берутся только из базы знаний и данных заявки (RAG-подход). Если включена
модель с открытыми весами — она формулирует ответ по найденным фрагментам;
иначе ответ собирается детерминированно.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.knowledge import search
from app.domain.statuses import STATUS_META, AppStatus
from app.models import Application
from app.services import llm
from app.services.applications import active_offer, client_explanation

SYSTEM = ("Ты помощник в кредитном кабинете для предпринимателей. Отвечай по-русски, кратко (до 5 предложений), "
          "простыми словами. Используй только факты из раздела «Контекст». Не обещай одобрение, не давай "
          "инвестиционных или юридических советов. Если в контексте нет ответа — скажи, что не знаешь, и предложи "
          "посмотреть статус заявки или подобрать продукт.")


def app_context(session: Session, app: Application) -> str:
    meta = STATUS_META[AppStatus(app.status)]
    parts = [f"Заявка {app.number}: продукт «{app.product.name}», {float(app.amount):,.0f} ₽ на {app.term_months} мес. "
             f"Статус: {meta.client_label}. {meta.client_hint}".replace(",", " ")]
    offer = active_offer(session, app)
    if offer:
        parts.append(f"Предложение: {float(offer.amount):,.0f} ₽, {offer.term_months} мес., ставка {float(offer.rate):.2f}%, "
                     f"платёж {float(offer.monthly_payment):,.0f} ₽/мес., переплата {float(offer.overpayment):,.0f} ₽.".replace(",", " "))
        if offer.changes:
            parts.append("Изменения относительно запроса: " + "; ".join(offer.changes))
    expl = client_explanation(session, app)
    if expl and expl["outcome"] == "decline":
        parts.append("Причины отказа: " + "; ".join(r["text"] for r in expl["reasons"] if r.get("text")))
        if expl["plan"]:
            parts.append("Что сделать: " + "; ".join(expl["plan"][:3]))
    return "\n".join(parts)


def answer(session: Session, question: str, app: Application | None) -> dict:
    hits = search(question)
    ctx_parts = [f"{h['title']}: {h['text']}" for h in hits]
    q = question.lower()
    about_app = app is not None and any(w in q for w in ("заявк", "статус", "почему", "отказ", "предложен", "платеж",
                                                          "платёж", "когда", "сколько", "мой", "моя", "мне"))
    if app is not None:
        ctx_parts.insert(0, app_context(session, app))
    context = "\n\n".join(ctx_parts)
    sources = [{"id": h["id"], "title": h["title"]} for h in hits]
    if app is not None:
        sources.insert(0, {"id": "application", "title": f"Ваша заявка {app.number}"})
    text = llm.chat(SYSTEM, f"Контекст:\n{context}\n\nВопрос: {question}")
    if text:
        return {"answer": text, "sources": sources, "provider": "llm"}
    if about_app and app is not None:
        body = app_context(session, app)
        if hits:
            body += "\n\n" + hits[0]["text"]
        return {"answer": body, "sources": sources, "provider": "rules"}
    if hits:
        return {"answer": "\n\n".join(h["text"] for h in hits[:2]), "sources": sources, "provider": "rules"}
    return {"answer": "Пока не знаю ответа на этот вопрос. Посмотрите статус заявки на её странице или воспользуйтесь "
                      "подбором финансирования — там объяснены условия каждого продукта.",
            "sources": [], "provider": "rules"}
