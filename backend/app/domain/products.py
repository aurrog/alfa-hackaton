"""Кредитные продукты: условия, доступность для компании и подбор по задаче клиента."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.calculator import annuity_payment
from app.domain.okved import sector_by_okved

PURPOSES: dict[str, dict[str, str]] = {
    "working_capital": {"title": "Пополнить оборотные средства", "hint": "Закупка товара и сырья, сезонные запасы, зарплаты и аренда"},
    "equipment": {"title": "Купить оборудование или транспорт", "hint": "Станки, техника, автомобили, кассовое и торговое оборудование"},
    "cash_gap": {"title": "Закрыть кассовый разрыв", "hint": "Деньги нужны регулярно, на короткий срок, пока покупатели не заплатили"},
    "contract": {"title": "Исполнить контракт", "hint": "Госзаказ или крупный заказчик: закупка и работы до оплаты"},
    "expansion": {"title": "Развить бизнес", "hint": "Новая точка, ремонт, новое направление"},
    "any": {"title": "Другие цели бизнеса", "hint": "Любые законные цели, связанные с бизнесом"},
}


@dataclass
class ProductSpec:
    code: str
    name: str
    kind: str  # term_loan | overdraft | credit_line
    purposes: list[str]
    min_amount: float
    max_amount: float
    min_term: int
    max_term: int
    rate_mode: str = "spread"  # spread — ключевая + спред; key_rate — ставка равна ключевой
    rate_spread: float = 5.0
    min_business_age_months: int = 6
    requires_bank_client: bool = False
    min_bank_client_months: int = 0
    collateral_required_from: float | None = None
    turnover_multiple: float | None = None  # максимум суммы в месячных оборотах (для беззалоговых)
    auto_decision: bool = True
    gov_program: bool = False
    legal_forms: list[str] = field(default_factory=lambda: ["IP", "LE"])
    decision_time: str = ""

    def base_rate(self, key_rate: float) -> float:
        return round(key_rate if self.rate_mode == "key_rate" else key_rate + self.rate_spread, 2)


@dataclass
class CompanyProfile:
    inn: str
    legal_form: str  # IP | LE
    okved_code: str | None
    region_code: str | None
    registration_date: date | None
    status: str = "active"
    msp_category: str | None = None
    is_bank_client: bool = False
    bank_client_months: int = 0
    avg_monthly_turnover: float | None = None

    def age_months(self, today: date | None = None) -> int | None:
        if not self.registration_date:
            return None
        today = today or date.today()
        return (today.year - self.registration_date.year) * 12 + today.month - self.registration_date.month - (
            1 if today.day < self.registration_date.day else 0)


@dataclass
class Need:
    purpose: str = "any"
    amount: float = 1_000_000
    term_months: int = 12
    urgent: bool = False
    regular: bool = False  # потребность повторяется (оборот, кассовые разрывы)
    has_collateral: bool = False


def eligibility(p: ProductSpec, c: CompanyProfile, amount: float | None = None, term: int | None = None,
                today: date | None = None) -> list[str]:
    """Причины, по которым продукт недоступен (пустой список — доступен)."""
    reasons: list[str] = []
    if c.legal_form not in p.legal_forms:
        reasons.append("Продукт доступен только для " + ("ИП" if p.legal_forms == ["IP"] else "юридических лиц"))
    if c.status != "active":
        reasons.append("Компания не в статусе «действующая» по данным ЕГРЮЛ/ЕГРИП")
    age = c.age_months(today)
    if age is not None and age < p.min_business_age_months:
        reasons.append(f"Нужен срок работы бизнеса от {p.min_business_age_months} мес. (сейчас {age} мес.)")
    if p.requires_bank_client and (not c.is_bank_client or c.bank_client_months < p.min_bank_client_months):
        reasons.append(f"Нужен расчётный счёт в банке от {p.min_bank_client_months} мес. с оборотами")
    if p.gov_program:
        sector = sector_by_okved(c.okved_code)
        if not sector.gov_priority:
            reasons.append(f"Отрасль «{sector.name}» не входит в приоритетные отрасли программы")
        if not c.msp_category:
            reasons.append("Компания должна быть в Едином реестре субъектов МСП")
    if amount is not None and not (p.min_amount <= amount <= p.max_amount):
        reasons.append(f"Сумма от {p.min_amount:,.0f} до {p.max_amount:,.0f} ₽".replace(",", " "))
    if term is not None and not (p.min_term <= term <= p.max_term):
        reasons.append(f"Срок от {p.min_term} до {p.max_term} мес.")
    return reasons


def recommend(products: list[ProductSpec], need: Need, company: CompanyProfile, key_rate: float,
              preapproved: dict[str, float] | None = None, today: date | None = None) -> list[dict]:
    """Подбор продуктов под задачу клиента с объяснением «почему подходит»."""
    preapproved = preapproved or {}
    out = []
    for p in products:
        pros: list[str] = []
        warnings: list[str] = []
        score = 0.0
        if need.purpose in p.purposes:
            score += 3
            pros.append(f"Подходит для цели «{PURPOSES.get(need.purpose, {}).get('title', need.purpose)}»")
        elif "any" in p.purposes:
            score += 1
            pros.append("Можно направить на любые цели бизнеса")
        else:
            score -= 3
            warnings.append("Продукт рассчитан на другие цели")

        term = min(max(need.term_months, p.min_term), p.max_term)
        if term != need.term_months:
            # продукт не даёт нужный срок — платёж будет другим, чем клиент рассчитывал
            score -= 2
            warnings.append(f"Срок скорректирован до {term} мес. (условия продукта)")
        amount = need.amount
        blockers = eligibility(p, company, None, None, today)
        if amount > p.max_amount:
            blockers.append(f"Максимальная сумма по продукту — {p.max_amount:,.0f} ₽".replace(",", " "))
        if amount < p.min_amount:
            # не навязываем больше, чем нужно: продукт с минимумом выше запроса — только альтернатива
            score -= 2
            warnings.append(f"Минимальная сумма — {p.min_amount:,.0f} ₽".replace(",", " "))
            amount = p.min_amount

        if need.urgent and p.auto_decision:
            score += 2
            pros.append(p.decision_time or "Быстрое автоматическое решение")
        if need.regular and p.kind in ("overdraft", "credit_line"):
            score += 3
            pros.append("Лимит можно использовать многократно — проценты только за фактически взятые деньги")
        if p.kind in ("overdraft", "credit_line") and not need.regular and need.purpose in ("equipment", "expansion"):
            score -= 2
        if p.collateral_required_from is not None and amount >= p.collateral_required_from:
            if need.has_collateral:
                score += 1
                pros.append("Залог снижает ставку")
            else:
                score -= 1
                warnings.append(f"От {p.collateral_required_from:,.0f} ₽ потребуется залог".replace(",", " "))
        if p.gov_program and not blockers:
            score += 3
            pros.append("Льготная ставка: равна ключевой ставке Банка России")
        if p.code in preapproved:
            limit = preapproved[p.code]
            if amount <= limit:
                score += 3
                pros.append(f"Предварительно одобрено до {limit:,.0f} ₽ — без документов".replace(",", " "))
            else:
                warnings.append(f"Предодобренный лимит — {limit:,.0f} ₽".replace(",", " "))
        if p.turnover_multiple and company.avg_monthly_turnover:
            cap = p.turnover_multiple * company.avg_monthly_turnover
            if amount > cap:
                warnings.append(f"По оборотам в банке ориентир суммы — до {cap:,.0f} ₽".replace(",", " "))

        base = p.base_rate(key_rate)
        payment = annuity_payment(amount, base, term) if p.kind == "term_loan" else amount * base / 100 / 12
        out.append({
            "code": p.code,
            "name": p.name,
            "eligible": not blockers,
            "score": round(score, 2),
            "pros": pros,
            "warnings": warnings,
            "blockers": blockers,
            "rate_from": base,
            "term_months": term,
            "amount": amount,
            "monthly_payment_from": round(payment, 2),
            "payment_kind": "annuity" if p.kind == "term_loan" else "interest_only",
        })
    # при равных баллах выше — продукт с меньшей ставкой
    out.sort(key=lambda r: (not r["eligible"], -r["score"], r["rate_from"]))
    if out and out[0]["eligible"]:
        out[0]["best"] = True
    return out
