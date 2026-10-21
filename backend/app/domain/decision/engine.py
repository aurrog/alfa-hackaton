"""Движок кредитного решения.

Разделение ответственности (как в кейсе: «скоринг ≠ кредитное решение»):
  * скоринг (domain/scoring) оценивает риск заёмщика → балл, PD, грейд;
  * движок применяет кредитную политику: стоп-факторы, триггеры ручной проверки,
    ценообразование по грейду, расчёт посильной суммы (DSCR), лимиты продукта,
    залог, полномочия — и формирует рекомендацию и маршрут заявки.

Одинаковый грейд даёт разные условия для разных продуктов: у продуктов
свои спреды, лимиты, требования к залогу и обороту.

Чистая функция без БД и сети — легко тестировать и воспроизводить.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.domain.calculator import annuity_payment, max_principal, round_down
from app.domain.decision.policy import Policy
from app.domain.okved import sector_by_okved
from app.domain.products import ProductSpec
from app.domain.scoring import ScoreResult


def _pct(x: float, digits: int = 1) -> str:
    """Процент в русской записи: 0.078 → «7,8%»."""
    return f"{x * 100:.{digits}f}%".replace(".", ",")


COLLATERAL_TITLES = {
    "real_estate": "недвижимость", "equipment": "оборудование", "vehicle": "транспорт",
    "goods": "товары в обороте", "guarantee_fund": "поручительство гарантийного фонда",
}

CRITICAL_SOURCES = {"egrul": "ЕГРЮЛ/ЕГРИП", "bki_company": "БКИ (компания)", "bki_owner": "БКИ (собственник)"}


@dataclass
class Check:
    code: str
    title: str
    result: str  # pass | warn | fail | unavailable | info
    effect: str | None  # stop | manual | None
    details: str
    source: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class DecisionContext:
    product: ProductSpec
    amount: float
    term: int
    purpose: str
    legal_form: str
    okved_code: str | None
    collateral_type: str | None = None
    collateral_value: float | None = None
    company_status: str = "active"
    aml_hit: bool = False
    disqualified_director: bool = False
    mass_address: bool = False
    blocked_accounts: bool = False
    registry_mismatches: list[str] = field(default_factory=list)
    in_msp_registry: bool = True
    business_age_months: int | None = None
    monthly_revenue: float | None = None  # подтверждённая выручка, ₽/мес
    revenue_source: str = "нет данных"
    declared_monthly_revenue: float | None = None
    existing_monthly_payments: float = 0.0
    company_max_overdue_days: int | None = 0
    owner_max_overdue_days: int | None = 0
    tax_arrears: float = 0.0
    bank_client_months: int = 0
    unavailable_sources: list[str] = field(default_factory=list)
    sticky_manual: bool = False
    score: ScoreResult | None = None


@dataclass
class Recommendation:
    outcome: str  # approve | counter_offer | decline
    route: str  # auto_offer | auto_decline | refer
    amount: float | None
    term: int | None
    rate: float | None
    monthly_payment: float | None
    conditions: list[str]
    reason_codes: list[dict]
    counter_changes: list[str]
    manual_reasons: list[str]
    required_level: str  # auto | analyst | senior_analyst | committee
    affordability: dict
    explanation: dict
    checks: list[Check]
    policy_version: int

    def as_dict(self) -> dict:
        d = asdict(self)
        d["checks"] = [c.as_dict() for c in self.checks]
        return d


# --------------------------------------------------------------------------
# Правила политики → проверки (они же показываются аналитику и клиенту)
# --------------------------------------------------------------------------
def policy_checks(ctx: DecisionContext, policy: Policy) -> list[Check]:
    checks: list[Check] = []
    add = checks.append
    p = ctx.product

    for src, title in CRITICAL_SOURCES.items():
        if src in ctx.unavailable_sources:
            add(Check(f"SOURCE_{src.upper()}", f"Источник «{title}» недоступен", "unavailable", "manual",
                      "Сведения не получены после повторных попыток — требуется ручная проверка", title))

    if "egrul" not in ctx.unavailable_sources:
        if ctx.company_status != "active":
            add(Check("STOP_COMPANY_STATUS", "Статус компании по ЕГРЮЛ/ЕГРИП", "fail", "stop",
                      f"Статус: {ctx.company_status}", "ЕГРЮЛ/ЕГРИП"))
        else:
            add(Check("STOP_COMPANY_STATUS", "Статус компании по ЕГРЮЛ/ЕГРИП", "pass", None, "Действующая", "ЕГРЮЛ/ЕГРИП"))
        if ctx.registry_mismatches:
            add(Check("REGISTRY_MISMATCH", "Сверка анкеты с ЕГРЮЛ/ЕГРИП", "warn", "manual",
                      "; ".join(ctx.registry_mismatches), "ЕГРЮЛ/ЕГРИП"))
        else:
            add(Check("REGISTRY_MISMATCH", "Сверка анкеты с ЕГРЮЛ/ЕГРИП", "pass", None, "Данные анкеты совпадают с реестром", "ЕГРЮЛ/ЕГРИП"))
        age = ctx.business_age_months
        if age is not None and age < p.min_business_age_months:
            add(Check("STOP_BUSINESS_AGE", "Срок ведения бизнеса", "fail", "stop",
                      f"{age} мес. при требовании продукта от {p.min_business_age_months} мес.", "ЕГРЮЛ/ЕГРИП"))
        elif age is not None:
            add(Check("STOP_BUSINESS_AGE", "Срок ведения бизнеса", "pass", None, f"{age} мес.", "ЕГРЮЛ/ЕГРИП"))

    add(Check("STOP_AML", "Проверка по перечням и стоп-листам (115-ФЗ)", "fail" if ctx.aml_hit else "pass",
              "stop" if ctx.aml_hit else None, "Совпадение в перечнях" if ctx.aml_hit else "Совпадений нет", "Стоп-листы"))
    add(Check("STOP_DISQUALIFIED", "Дисквалификация руководителя", "fail" if ctx.disqualified_director else "pass",
              "stop" if ctx.disqualified_director else None,
              "Руководитель в реестре дисквалифицированных лиц" if ctx.disqualified_director else "Нет сведений", "ФНС"))
    if ctx.mass_address:
        add(Check("MASS_ADDRESS", "Адрес массовой регистрации", "warn", "manual", "Адрес отмечен ФНС как адрес массовой регистрации", "ФНС"))
    if ctx.blocked_accounts:
        add(Check("BLOCKED_ACCOUNTS", "Приостановление операций по счетам", "warn", "manual",
                  "Есть действующие решения ФНС о приостановлении операций", "ФНС"))

    stop_days = policy["hard_stop_overdue_days"]
    warn_days = policy["warn_overdue_days"]
    overdue_checks = [("OVERDUE_COMPANY", "Просрочки заёмщика за 24 мес.", ctx.company_max_overdue_days, "bki_company")]
    if ctx.legal_form == "LE":  # для ИП заёмщик и собственник — одно лицо
        overdue_checks.append(("OVERDUE_OWNER", "Просрочки собственника за 24 мес.", ctx.owner_max_overdue_days, "bki_owner"))
    for code, title, days, src in overdue_checks:
        if src in ctx.unavailable_sources or days is None:
            continue
        if days >= stop_days:
            add(Check(code, title, "fail", "stop", f"Максимальная просрочка {days} дн. (стоп-фактор от {stop_days} дн.)", "БКИ"))
        elif days >= warn_days:
            add(Check(code, title, "warn", "manual", f"Максимальная просрочка {days} дн.", "БКИ"))
        elif days > 0:
            add(Check(code, title, "info", None, f"Максимальная просрочка {days} дн. — учтено в скоринге", "БКИ"))
        else:
            add(Check(code, title, "pass", None, "Просрочек нет", "БКИ"))

    if ctx.tax_arrears > 0:
        ratio = ctx.tax_arrears / ctx.monthly_revenue if ctx.monthly_revenue else 1.0
        stop = ctx.tax_arrears >= policy["tax_arrears_stop_amount"] and ratio >= policy["tax_arrears_stop_ratio"]
        add(Check("TAX_ARREARS", "Задолженность по налогам и сборам", "fail" if stop else "info", "stop" if stop else None,
                  f"{ctx.tax_arrears:,.0f} ₽ ({ratio:.0%} месячной выручки)".replace(",", " "), "ФНС"))
    else:
        add(Check("TAX_ARREARS", "Задолженность по налогам и сборам", "pass", None, "Нет задолженности", "ФНС"))

    if p.gov_program:
        sector = sector_by_okved(ctx.okved_code)
        ok = sector.gov_priority and ctx.in_msp_registry
        add(Check("GOV_ELIGIBILITY", "Соответствие условиям программы господдержки", "pass" if ok else "fail",
                  None if ok else "stop",
                  f"Отрасль: {sector.name}; реестр МСП: {'да' if ctx.in_msp_registry else 'нет'}", "Реестр МСП"))
        if ok:
            add(Check("GOV_LIMIT", "Лимит программы и поручительство Корпорации МСП", "info", "manual",
                      "Решение по льготной программе принимает специалист (проверка лимита)", "Политика"))

    if ctx.declared_monthly_revenue and ctx.monthly_revenue and ctx.revenue_source != "анкета":
        dev = abs(ctx.declared_monthly_revenue - ctx.monthly_revenue) / ctx.monthly_revenue
        if dev > policy["turnover_deviation_manual"]:
            add(Check("REVENUE_DEVIATION", "Сверка заявленной выручки с подтверждённой", "warn", "manual",
                      f"Расхождение {dev:.0%}: заявлено {ctx.declared_monthly_revenue:,.0f} ₽/мес, "
                      f"по данным ({ctx.revenue_source}) {ctx.monthly_revenue:,.0f} ₽/мес".replace(",", " "), ctx.revenue_source))
        else:
            add(Check("REVENUE_DEVIATION", "Сверка заявленной выручки с подтверждённой", "pass", None,
                      f"Расхождение {dev:.0%}", ctx.revenue_source))
    if ctx.revenue_source == "анкета":
        add(Check("REVENUE_UNVERIFIED", "Подтверждение выручки", "warn", "manual",
                  "Выручка известна только со слов клиента", "Анкета"))

    if ctx.score is not None:
        g = ctx.score.grade
        if g in policy["decline_grades"]:
            add(Check("SCORE_GRADE", "Скоринговая оценка", "fail", "stop", f"Грейд {g}, PD {_pct(ctx.score.pd)}", "Скоринг"))
        elif g in policy["manual_grades"]:
            add(Check("SCORE_GRADE", "Скоринговая оценка", "warn", "manual", f"Грейд {g}, PD {_pct(ctx.score.pd)} — пограничная зона", "Скоринг"))
        else:
            add(Check("SCORE_GRADE", "Скоринговая оценка", "pass", None, f"Грейд {g}, PD {_pct(ctx.score.pd)}", "Скоринг"))
        if ctx.score.incomplete:
            add(Check("SCORE_INCOMPLETE", "Полнота данных для скоринга", "warn", "manual",
                      "Часть факторов оценена консервативно из-за отсутствия данных", "Скоринг"))
    return checks


# --------------------------------------------------------------------------
# Ценообразование и посильная сумма
# --------------------------------------------------------------------------
def price(ctx: DecisionContext, policy: Policy, grade: str, secured: bool) -> float:
    p = ctx.product
    key = float(policy["key_rate"])
    if p.rate_mode == "key_rate":
        return round(key, 2)
    rate = key + p.rate_spread + float(policy["grade_premium"].get(grade, 8.0))
    if ctx.bank_client_months >= 12:
        rate -= float(policy["discount_bank_client"])
    if secured:
        rate -= float(policy["discount_secured"])
    return round(rate, 2)


def _service(amount: float, rate: float, term: int, kind: str) -> float:
    """Ежемесячная нагрузка: аннуитет для срочного кредита; для лимитов —
    проценты плюс условное погашение основного долга за срок."""
    if kind == "term_loan":
        return annuity_payment(amount, rate, term)
    return amount * rate / 1200 + amount / term


def affordability(ctx: DecisionContext, policy: Policy, rate: float, term: int, secured: bool) -> dict:
    p = ctx.product
    sector = sector_by_okved(ctx.okved_code)
    revenue = ctx.monthly_revenue or 0.0
    ocf = revenue * sector.margin * float(policy["margin_multiplier"])
    max_payment = max(ocf / float(policy["min_dscr"]) - ctx.existing_monthly_payments, 0.0)
    if p.kind == "term_loan":
        by_dscr = max_principal(max_payment, rate, term)
    else:
        by_dscr = max_payment / (rate / 1200 + 1 / term) if max_payment > 0 else 0.0
    caps = {"product_max": p.max_amount, "dscr": by_dscr}
    if p.turnover_multiple and revenue:
        caps["turnover"] = p.turnover_multiple * revenue
    unsecured_limit = p.collateral_required_from
    if secured and ctx.collateral_value:
        ltv = policy["collateral_ltv"].get(ctx.collateral_type or "", 0.0)
        caps["collateral"] = ctx.collateral_value * ltv
    elif unsecured_limit is not None:
        caps["unsecured_limit"] = unsecured_limit - 1
    approved_max = round_down(max(min(caps.values()), 0.0), int(policy["round_step"]))
    binding = min(caps, key=caps.get)
    return {
        "monthly_revenue": round(revenue, 2),
        "revenue_source": ctx.revenue_source,
        "sector_margin": sector.margin,
        "operating_cash_flow": round(ocf, 2),
        "existing_payments": round(ctx.existing_monthly_payments, 2),
        "min_dscr": float(policy["min_dscr"]),
        "max_new_payment": round(max_payment, 2),
        "caps": {k: round(v, 2) for k, v in caps.items()},
        "binding_cap": binding,
        "approved_max": approved_max,
        "rate": rate,
        "term": term,
    }


def _dscr(ctx: DecisionContext, policy: Policy, amount: float, rate: float, term: int) -> float | None:
    sector = sector_by_okved(ctx.okved_code)
    ocf = (ctx.monthly_revenue or 0) * sector.margin * float(policy["margin_multiplier"])
    service = ctx.existing_monthly_payments + _service(amount, rate, term, ctx.product.kind)
    return round(ocf / service, 2) if service > 0 else None


# --------------------------------------------------------------------------
# Решение
# --------------------------------------------------------------------------
def decide(ctx: DecisionContext, policy: Policy) -> Recommendation:
    p = ctx.product
    score = ctx.score
    grade = score.grade if score else "E"
    checks = policy_checks(ctx, policy)
    stops = [c for c in checks if c.effect == "stop"]
    manual = [c for c in checks if c.effect == "manual"]
    manual_reasons = [f"{c.title}: {c.details}" for c in manual]
    if ctx.sticky_manual:
        manual_reasons.append("Заявка ранее направлялась на ручное рассмотрение")

    secured = bool(ctx.collateral_type and ctx.collateral_type != "none" and ctx.collateral_value)
    rate = price(ctx, policy, grade, secured)
    explanation = _explain(score)

    reason_codes: list[dict] = []
    for c in stops:
        if c.code == "SCORE_GRADE" and len(stops) > 1:
            continue  # грейд E — следствие стоп-факторов, отдельной причиной не показываем
        reason_codes.append(_reason(c.code, c.details, score))

    term = ctx.term
    aff = affordability(ctx, policy, rate, term, secured)
    outcome = "approve"
    amount = ctx.amount
    counter: list[str] = []

    if not stops:
        if amount > aff["approved_max"]:
            # 1) увеличить срок
            best = None
            for t in sorted({*range(term + 6, p.max_term + 1, 6), p.max_term}):
                if t <= term:
                    continue
                a = affordability(ctx, policy, rate, t, secured)
                if amount <= a["approved_max"]:
                    best = (t, a)
                    break
            if best:
                outcome = "counter_offer"
                counter.append(f"Срок увеличен с {term} до {best[0]} мес., чтобы платёж был посильным")
                term, aff = best
            else:
                # 2) уменьшить сумму (выбираем срок, дающий большую сумму)
                long_aff = affordability(ctx, policy, rate, p.max_term, secured)
                if long_aff["approved_max"] >= aff["approved_max"] * 1.15 and p.max_term > term:
                    counter.append(f"Срок увеличен с {term} до {p.max_term} мес.")
                    term, aff = p.max_term, long_aff
                new_amount = aff["approved_max"]
                if new_amount >= max(p.min_amount, ctx.amount * float(policy["counter_offer_min_share"])):
                    outcome = "counter_offer"
                    counter.insert(0, f"Сумма уменьшена с {ctx.amount:,.0f} до {new_amount:,.0f} ₽ — "
                                      f"с учётом денежного потока и текущей долговой нагрузки".replace(",", " "))
                    amount = new_amount
                    if aff["binding_cap"] == "unsecured_limit":
                        counter.append("Большую сумму можно получить под залог")
                else:
                    outcome = "decline"
                    reason_codes.append(_reason("LOW_AFFORDABILITY", f"Посильная сумма {new_amount:,.0f} ₽".replace(",", " "), score))
    else:
        outcome = "decline"

    if outcome == "decline":
        offered_amount = offered_rate = payment = None
        offered_term = None
    else:
        offered_amount, offered_term, offered_rate = amount, term, rate
        payment = round(_service(amount, rate, term, p.kind) if p.kind == "term_loan" else amount * rate / 1200, 2)
        aff["dscr_at_offer"] = _dscr(ctx, policy, amount, rate, term)

    conditions = _conditions(ctx, policy, outcome, secured, amount)

    # Маршрут и уровень полномочий
    if outcome != "decline" and amount > float(policy["auto_approve_max_amount"]):
        manual_reasons.append(f"Сумма выше лимита автоматического решения ({float(policy['auto_approve_max_amount']):,.0f} ₽)".replace(",", " "))
    if outcome != "decline" and grade not in policy["auto_approve_grades"] and not any(c.code == "SCORE_GRADE" and c.effect for c in checks):
        manual_reasons.append(f"Грейд {grade} не допускает автоматического одобрения")
    if outcome != "decline" and not p.auto_decision:
        manual_reasons.append("Продукт предусматривает решение специалиста")

    if ctx.sticky_manual:
        route = "refer"
        level = _level(policy, offered_amount or ctx.amount, grade)
    elif not manual_reasons:
        route = "auto_offer" if outcome != "decline" else "auto_decline"
        level = "auto"
    elif outcome == "decline" and stops and not any(c.result == "unavailable" for c in checks):
        # стоп-фактор надёжно подтверждён источником — ручная проверка не меняет результат
        route, level = "auto_decline", "auto"
        manual_reasons = []
    else:
        route = "refer"
        level = _level(policy, offered_amount or ctx.amount, grade)

    return Recommendation(
        outcome=outcome, route=route, amount=offered_amount, term=offered_term, rate=offered_rate,
        monthly_payment=payment, conditions=conditions, reason_codes=reason_codes, counter_changes=counter,
        manual_reasons=manual_reasons, required_level=level, affordability=aff, explanation=explanation,
        checks=checks, policy_version=policy.version,
    )


def required_level(policy: Policy, amount: float, grade: str) -> str:
    return _level(policy, amount, grade)


def _level(policy: Policy, amount: float, grade: str) -> str:
    limits = policy["authority_limits"]
    if grade in policy["committee_grades"]:
        return "committee"
    if amount <= limits["analyst"]:
        return "analyst"
    if amount <= limits["senior_analyst"]:
        return "senior_analyst"
    return "committee"


def _conditions(ctx: DecisionContext, policy: Policy, outcome: str, secured: bool, amount: float) -> list[str]:
    if outcome == "decline":
        return []
    out = []
    if ctx.legal_form == "LE":
        out.append("Поручительство собственника бизнеса (физического лица)")
    if secured:
        out.append(f"Залог: {COLLATERAL_TITLES.get(ctx.collateral_type or '', ctx.collateral_type)} "
                   f"оценочной стоимостью не менее {ctx.collateral_value:,.0f} ₽".replace(",", " "))
    if ctx.product.gov_program:
        out.append("Льготная программа: ставка равна ключевой ставке Банка России на дату выдачи, поручительство Корпорации МСП")
    if ctx.bank_client_months > 0:
        share = float(policy["covenant_turnover_share"])
        out.append(f"Поддерживать поступления на расчётный счёт в банке не ниже {share:.0%} среднемесячной выручки")
    if ctx.purpose == "equipment":
        out.append("Целевое использование: оплата по договору поставки, подтверждение — в течение 30 дней")
    if ctx.product.kind == "overdraft":
        out.append("Транши до 60 дней, ежемесячное полное погашение задолженности хотя бы на один день")
    return out


def _explain(score: ScoreResult | None) -> dict:
    if not score:
        return {"positives": [], "negatives": []}
    return {
        "positives": [{"title": f.title, "value": f.display_value, "label": f.bin_label} for f in score.positives(3)],
        "negatives": [{"title": f.title, "value": f.display_value, "label": f.bin_label,
                       "lost_points": f.lost_points, "hint": f.client_hint} for f in score.negatives(3)],
    }


REASONS: dict[str, dict[str, str]] = {
    "STOP_COMPANY_STATUS": {
        "client": "По данным ЕГРЮЛ/ЕГРИП компания не является действующей (ликвидация, реорганизация или банкротство).",
        "hint": "Кредит может получить только действующий бизнес. Если данные реестра устарели — обновите их через ФНС.",
    },
    "STOP_AML": {
        "client": "Банк не может предоставить кредит по результатам обязательных внутренних проверок.",
        "hint": "Подробности можно уточнить при обращении в банк.",
    },
    "STOP_DISQUALIFIED": {
        "client": "Руководитель компании числится в реестре дисквалифицированных лиц.",
        "hint": "Решение возможно после смены руководителя и внесения изменений в ЕГРЮЛ.",
    },
    "OVERDUE_COMPANY": {
        "client": "В кредитной истории заёмщика есть просрочка 90 дней и более за последние 24 месяца.",
        "hint": "Погасите просроченную задолженность. Через 6–12 месяцев платежей без просрочек оценка заметно улучшится.",
    },
    "OVERDUE_OWNER": {
        "client": "В кредитной истории собственника есть просрочка 90 дней и более за последние 24 месяца.",
        "hint": "Проверьте свою кредитную историю в БКИ и погасите просроченные долги.",
    },
    "TAX_ARREARS": {
        "client": "У компании есть существенная задолженность по налогам и сборам по данным ФНС.",
        "hint": "Погасите задолженность и пени. После обновления сведений ФНС подайте заявку снова — данные подставятся автоматически.",
    },
    "STOP_BUSINESS_AGE": {
        "client": "Срок работы бизнеса меньше, чем требуется по выбранному продукту.",
        "hint": "Выберите продукт для молодого бизнеса или подайте заявку, когда бизнес достигнет нужного срока.",
    },
    "GOV_ELIGIBILITY": {
        "client": "Компания не соответствует условиям программы господдержки (отрасль или реестр МСП).",
        "hint": "Подойдут продукты на рыночных условиях — воспользуйтесь подбором финансирования.",
    },
    "SCORE_GRADE": {
        "client": "Совокупная оценка кредитного риска выше допустимого уровня.",
        "hint": "Обратите внимание на факторы, которые сильнее всего снизили оценку: их улучшение повысит шансы.",
    },
    "LOW_AFFORDABILITY": {
        "client": "Денежного потока бизнеса недостаточно для обслуживания кредита даже на минимальную сумму продукта.",
        "hint": "Снизьте текущую долговую нагрузку или предоставьте залог / поручительство гарантийного фонда.",
    },
}


def _reason(code: str, details: str, score: ScoreResult | None) -> dict:
    r = REASONS.get(code, {"client": details, "hint": ""})
    return {"code": code, "client_text": r["client"], "hint": r["hint"], "details": details}
