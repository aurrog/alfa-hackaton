"""Персональная лента новостей клиента.

Контентная рекомендательная модель с объяснением:
  релевантность = приоритет + свежесть
                + совпадения аудитории (отрасль, регион, форма бизнеса, размер,
                  статус в банке, этап кредитного пути, причины отказа)
                + выученные интересы (клики, лайки, скрытия) и выбранные темы
затем — переранжирование на разнообразие (не больше двух подряд из одной рубрики).

Для каждой карточки возвращается «почему вы это видите» — лента прозрачна
так же, как кредитное решение.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

STAGE_TITLES = {
    "none": "у вас пока нет заявок",
    "draft": "у вас есть незавершённая заявка",
    "info_requested": "по заявке нужны уточнения",
    "manual_review": "заявку рассматривает специалист",
    "committee_review": "заявку рассматривает кредитный комитет",
    "offer_issued": "вам направлено кредитное предложение",
    "offer_accepted": "вы готовитесь подписать договор",
    "issued": "у вас есть действующий кредит",
    "declined": "по вашей заявке было отказано",
}

WEIGHTS = {
    "sectors": 3.0, "regions": 1.5, "legal_forms": 1.0, "msp_categories": 1.0, "bank_client": 1.0,
    "stages": 4.0, "decline_reasons": 4.0, "gov_priority": 2.5, "products": 2.0,
}

LEGAL_FORM_TITLES = {"IP": "индивидуальных предпринимателей", "LE": "юридических лиц"}
MSP_TITLES = {"micro": "микропредприятие", "small": "малое предприятие", "medium": "среднее предприятие"}


@dataclass
class FeedProfile:
    sector_key: str
    sector_name: str
    region_code: str | None
    region_name: str
    legal_form: str
    msp_category: str | None
    bank_client: bool
    gov_priority: bool
    stages: set[str] = field(default_factory=set)
    decline_reasons: set[str] = field(default_factory=set)
    products: set[str] = field(default_factory=set)


@dataclass
class Interactions:
    hidden: set[str] = field(default_factory=set)
    opened: set[str] = field(default_factory=set)
    topic_weights: dict[str, float] = field(default_factory=dict)  # выученные интересы
    selected_topics: set[str] = field(default_factory=set)  # явно выбранные темы


def _match(dim: str, aud_val, p: FeedProfile) -> tuple[bool, str]:
    if dim == "sectors":
        return p.sector_key in aud_val, f"ваша отрасль — {p.sector_name.lower()}"
    if dim == "regions":
        return (p.region_code or "") in aud_val, f"ваш регион — {p.region_name}"
    if dim == "legal_forms":
        return p.legal_form in aud_val, f"материал для {LEGAL_FORM_TITLES.get(p.legal_form, p.legal_form)}"
    if dim == "msp_categories":
        return (p.msp_category or "") in aud_val, f"ваш бизнес — {MSP_TITLES.get(p.msp_category or '', 'МСП')}"
    if dim == "bank_client":
        return bool(aud_val) == p.bank_client, "вы клиент банка" if p.bank_client else "у вас пока нет счёта в банке"
    if dim == "stages":
        hit = p.stages & set(aud_val)
        stage = next(iter(sorted(hit)), "")
        return bool(hit), STAGE_TITLES.get(stage, "этап вашей заявки")
    if dim == "decline_reasons":
        return bool(p.decline_reasons & set(aud_val)), "это поможет устранить причину отказа"
    if dim == "gov_priority":
        return bool(aud_val) == p.gov_priority, "ваша отрасль входит в приоритетные для господдержки"
    if dim == "products":
        return bool(p.products & set(aud_val)), "вы интересовались этим продуктом"
    return False, ""


def rank(items: list[dict], profile: FeedProfile, inter: Interactions, today: date, limit: int = 12) -> list[dict]:
    scored = []
    for it in items:
        if it["id"] in inter.hidden:
            continue
        aud: dict = it.get("audience") or {}
        strict = set(it.get("strict") or [])
        score = 0.6 * float(it.get("priority", 0))
        age_days = max((today - date.fromisoformat(it["published_at"])).days, 0)
        score += 2.0 * math.exp(-age_days / 21)
        reasons: list[str] = []
        excluded = False
        for dim, val in aud.items():
            ok, why = _match(dim, val, profile)
            if ok:
                score += WEIGHTS.get(dim, 1.0)
                reasons.append(why)
            elif dim in strict:
                excluded = True
                break
            else:
                score -= 0.5
        if excluded:
            continue
        topics = it.get("topics") or []
        learned = sum(inter.topic_weights.get(t, 0.0) for t in topics)
        if learned:
            score += max(min(learned, 3.0), -3.0) * 0.8
            if learned > 0.5:
                reasons.append("похоже на материалы, которые вы открывали")
        if inter.selected_topics & set(topics):
            score += 1.5
            reasons.append("тема в ваших интересах")
        if it["id"] in inter.opened:
            score -= 0.3
        if not reasons:
            reasons.append("важно для всех предпринимателей" if it.get("priority", 0) >= 2 else "новое в ленте")
        scored.append({**it, "relevance": round(score, 3), "why": reasons})

    scored.sort(key=lambda x: (-x["relevance"], x["id"]))
    # Переранжирование на разнообразие рубрик
    result: list[dict] = []
    pool = scored[:]
    while pool and len(result) < limit:
        best_i, best_val = 0, -1e9
        for i, cand in enumerate(pool[:10]):
            same = sum(1 for r in result[-3:] if r["category"] == cand["category"])
            val = cand["relevance"] - 1.0 * same
            if val > best_val:
                best_i, best_val = i, val
        result.append(pool.pop(best_i))
    return result


def learn(topic_weights: dict[str, float], topics: list[str], action: str) -> dict[str, float]:
    """Онлайн-обновление интересов по действию пользователя."""
    delta = {"open": 0.5, "like": 1.0, "hide": -1.5, "view": 0.0}.get(action, 0.0)
    w = dict(topic_weights)
    for t in topics:
        w[t] = round(max(min(w.get(t, 0.0) + delta, 5.0), -5.0), 3)
    return w
