"""Персональная лента: профиль клиента из данных кабинета → ранжирование → инсайты."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.feed import FeedProfile, Interactions, learn, rank
from app.domain.okved import region_name, sector_by_okved
from app.models import Application, Company, Decision, FeedInteraction, FeedPreference, Loan, NewsItem, User
from app.services.applications import fetch_internal, internal_turnover
from app.services.common import today

CATEGORIES = {
    "support": "Господдержка", "taxes": "Налоги", "market": "Рынок", "product": "Продукты банка",
    "education": "Финграмотность", "regulation": "Законы", "industry": "Отрасль", "insight": "Для вас",
}
TOPICS = [
    {"code": "taxes", "title": "Налоги и отчётность"}, {"code": "gov_support", "title": "Господдержка"},
    {"code": "credit", "title": "Кредиты и ставки"}, {"code": "cashflow", "title": "Финансы бизнеса"},
    {"code": "horeca", "title": "Общепит"}, {"code": "trade", "title": "Торговля"},
    {"code": "construction", "title": "Стройка"}, {"code": "it", "title": "IT"},
    {"code": "agro", "title": "Агробизнес"}, {"code": "logistics", "title": "Логистика"},
    {"code": "manufacturing", "title": "Производство"}, {"code": "credit_history", "title": "Кредитная история"},
]


def profile(session: Session, company: Company) -> FeedProfile:
    sector = sector_by_okved(company.okved_code)
    apps = session.execute(select(Application).where(Application.company_id == company.id)).scalars().all()
    stages = {a.status for a in apps} or {"none"}
    if all(a.status in ("cancelled",) for a in apps):
        stages.add("none")
    reasons: set[str] = set()
    declined = [a.id for a in apps if a.status == "declined"]
    if declined:
        for d in session.execute(select(Decision).where(Decision.application_id.in_(declined), Decision.kind == "final")).scalars():
            reasons |= {r.get("code") for r in (d.reason_codes or []) if r.get("code")}
    has_loans = session.execute(select(Loan.id).where(Loan.company_id == company.id)).first() is not None
    if has_loans:
        stages.add("issued")
    return FeedProfile(
        sector_key=sector.key, sector_name=sector.name, region_code=company.region_code,
        region_name=region_name(company.region_code), legal_form=company.legal_form, msp_category=company.msp_category,
        bank_client=company.is_bank_client, gov_priority=sector.gov_priority, stages=stages, decline_reasons=reasons,
        products={a.product.code for a in apps},
    )


def interactions(session: Session, user: User) -> tuple[Interactions, FeedPreference | None]:
    pref = session.get(FeedPreference, user.id)
    rows = session.execute(select(FeedInteraction).where(FeedInteraction.user_id == user.id)).scalars().all()
    inter = Interactions(
        hidden={r.news_id for r in rows if r.action == "hide"},
        opened={r.news_id for r in rows if r.action in ("open", "like")},
        topic_weights=dict(pref.topic_weights) if pref else {},
        selected_topics=set(pref.selected_topics) if pref else set(),
    )
    return inter, pref


def insights(session: Session, company: Company, prof: FeedProfile) -> list[dict]:
    """Персональные карточки из данных банка — не новости, а подсказки по ситуации клиента.
    Предодобренное предложение показывается отдельным блоком на главной, в ленте его не дублируем."""
    cards: list[dict] = []
    if company.is_bank_client:
        abs_data = fetch_internal(session, company) or {}
        it = internal_turnover(abs_data)
        if it and it["months"] >= 6:
            months = abs_data.get("turnover_by_month") or []
            if len(months) >= 6:
                last3 = sum(m["incoming"] for m in months[-3:]) / 3
                prev3 = sum(m["incoming"] for m in months[-6:-3]) / 3
                if prev3 > 0:
                    growth = last3 / prev3 - 1
                    if growth > 0.1:
                        cards.append({
                            "id": f"insight-growth-{company.id}", "type": "insight", "category": "insight",
                            "title": f"Поступления на счёт выросли на {growth:.0%} за квартал",
                            "summary": "Рост оборотов учитывается в оценке: доступная сумма кредита и лимит овердрафта могут быть выше.",
                            "cta": {"label": "Подобрать финансирование", "link": "/products"},
                            "why": ["по данным вашего расчётного счёта"], "relevance": 50.0, "topics": ["cashflow"],
                        })
                    elif growth < -0.15:
                        cards.append({
                            "id": f"insight-drop-{company.id}", "type": "insight", "category": "insight",
                            "title": f"Поступления снизились на {abs(growth):.0%} за квартал",
                            "summary": "Если это сезонность — укажите это в комментарии к заявке. Для кассовых разрывов удобнее овердрафт.",
                            "cta": {"label": "Что такое овердрафт", "link": "/products?purpose=cash_gap"},
                            "why": ["по данным вашего расчётного счёта"], "relevance": 50.0, "topics": ["cashflow"],
                        })
    if "declined" in prof.stages:
        cards.append({
            "id": f"insight-declined-{company.id}", "type": "insight", "category": "insight",
            "title": "План: как получить одобрение в следующий раз",
            "summary": "В карточке отклонённой заявки — причины решения и конкретные шаги. Большинство факторов можно улучшить за 3–6 месяцев.",
            "cta": {"label": "Открыть заявки", "link": "/applications"},
            "why": ["по вашей заявке было отказано"], "relevance": 60.0, "topics": ["credit_history"],
        })
    return cards


def build_feed(session: Session, user: User, company: Company) -> dict:
    prof = profile(session, company)
    inter, _ = interactions(session, user)
    items = [{
        "id": n.id, "title": n.title, "summary": n.summary, "body": n.body, "category": n.category, "topics": n.topics or [],
        "audience": n.audience or {}, "strict": n.strict or [], "priority": n.priority,
        "published_at": n.published_at.isoformat(), "source": n.source, "cta": n.cta,
    } for n in session.execute(select(NewsItem).where(NewsItem.is_active.is_(True))).scalars()]
    ranked = rank(items, prof, inter, today())
    liked = {r.news_id for r in session.execute(select(FeedInteraction).where(
        FeedInteraction.user_id == user.id, FeedInteraction.action == "like")).scalars()}
    cards = [c for c in insights(session, company, prof) if c["id"] not in inter.hidden]
    for c in cards:
        c["category_title"] = CATEGORIES["insight"]
    for r in ranked:
        cards.append({**{k: r[k] for k in ("id", "title", "summary", "body", "category", "topics", "published_at",
                                            "source", "cta", "relevance", "why")},
                      "type": "news", "category_title": CATEGORIES.get(r["category"], r["category"]),
                      "liked": r["id"] in liked})
    return {
        "profile": {"sector": prof.sector_name, "region": prof.region_name,
                    "legal_form": "ИП" if prof.legal_form == "IP" else "ЮЛ", "msp_category": prof.msp_category,
                    "bank_client": prof.bank_client, "gov_priority": prof.gov_priority, "stages": sorted(prof.stages),
                    "learned_topics": {k: v for k, v in (inter.topic_weights or {}).items() if v}},
        "cards": cards,
        "topics": TOPICS,
        "selected_topics": sorted(inter.selected_topics),
    }


def record_action(session: Session, user: User, news_id: str, action: str, company_id: uuid.UUID | None) -> None:
    session.add(FeedInteraction(user_id=user.id, company_id=company_id, news_id=news_id, action=action))
    if news_id.startswith("insight-"):
        return
    news = session.get(NewsItem, news_id)
    topics = (news.topics if news else []) or []
    pref = session.get(FeedPreference, user.id)
    if pref is None:
        pref = FeedPreference(user_id=user.id, selected_topics=[], topic_weights={})
        session.add(pref)
    pref.topic_weights = learn(pref.topic_weights or {}, topics, action)


def set_topics(session: Session, user: User, topics: list[str]) -> None:
    allowed = {t["code"] for t in TOPICS}
    pref = session.get(FeedPreference, user.id)
    if pref is None:
        pref = FeedPreference(user_id=user.id, selected_topics=[], topic_weights={})
        session.add(pref)
    pref.selected_topics = [t for t in topics if t in allowed]
