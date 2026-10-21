"""Формирование кредитного предложения и рендер договора."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from jinja2 import Environment, select_autoescape
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domain.calculator import loan_summary, schedule
from app.domain.decision.policy import Policy
from app.models import Application, Decision, Offer
from app.services.common import today, utcnow


def create_offer(session: Session, app: Application, decision: Decision, *, amount: float, term: int, rate: float,
                 conditions: list[str], changes: list[str], policy: Policy) -> Offer:
    session.execute(update(Offer).where(Offer.application_id == app.id, Offer.status == "active")
                    .values(status="superseded"))
    if app.product.kind == "term_loan":
        s = loan_summary(amount, rate, term)
    else:  # лимит: проценты при полном использовании
        monthly = amount * rate / 1200
        s = {"monthly_payment": round(monthly, 2), "total_payment": round(monthly * term + amount, 2),
             "overpayment": round(monthly * term, 2), "effective_rate": round(((1 + rate / 1200) ** 12 - 1) * 100, 3)}
    is_counter = bool(changes) or abs(amount - float(app.amount)) > 1 or term != app.term_months
    offer = Offer(
        application_id=app.id, decision_id=decision.id, amount=Decimal(str(amount)), term_months=term,
        rate=Decimal(str(rate)), monthly_payment=Decimal(str(s["monthly_payment"])),
        total_payment=Decimal(str(s["total_payment"])), overpayment=Decimal(str(s["overpayment"])),
        effective_rate=Decimal(str(s["effective_rate"])), conditions=conditions, changes=changes, is_counter=is_counter,
        status="active", expires_at=utcnow() + timedelta(days=int(policy["offer_validity_days"])),
    )
    session.add(offer)
    session.flush()
    return offer


def offer_schedule(offer: Offer, kind: str, start=None) -> list[dict]:
    start = start or today()
    if kind != "term_loan":
        return []
    return [r.as_dict() for r in schedule(float(offer.amount), float(offer.rate), offer.term_months, start)]


_env = Environment(autoescape=select_autoescape(["html"]))

CONTRACT_TEMPLATE = _env.from_string("""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>{{ t.contract_number }}</title>
<style>
 body{font-family:Georgia,serif;max-width:760px;margin:24px auto;color:#1b1b1f;line-height:1.5;padding:0 16px}
 h1{font-size:20px;text-align:center} h2{font-size:15px;margin-top:20px}
 table{border-collapse:collapse;width:100%;font-size:13px} td,th{border:1px solid #bbb;padding:4px 6px;text-align:right}
 th{background:#f3f3f3} .muted{color:#666;font-size:12px} .stamp{border:2px solid #2e7d32;color:#2e7d32;padding:8px 12px;display:inline-block;margin-top:12px}
</style></head><body>
<p class="muted">Демонстрационный документ прототипа. Не является офертой. Все данные синтетические.</p>
<h1>Кредитный договор № {{ t.contract_number }}</h1>
<p>Банк (далее — «Кредитор») и {{ t.borrower.name }}, ИНН {{ t.borrower.inn }}, ОГРН {{ t.borrower.ogrn }},
адрес: {{ t.borrower.address }} (далее — «Заёмщик»), заключили настоящий договор о нижеследующем.</p>
<h2>1. Предмет договора</h2>
<p>Кредитор предоставляет Заёмщику кредит по продукту «{{ t.product }}» в сумме <b>{{ money(t.amount) }} ₽</b>
на срок <b>{{ t.term_months }} мес.</b> под <b>{{ pct(t.rate) }}% годовых</b>
(эффективная ставка без учёта комиссий — {{ pct(t.effective_rate) }}%).
Кредит зачисляется на расчётный счёт Заёмщика № {{ t.settlement_account or '—' }}.</p>
<h2>2. Порядок погашения</h2>
<p>Ежемесячный платёж — {{ money(t.monthly_payment) }} ₽. Общая сумма выплат — {{ money(t.total_payment) }} ₽.
График платежей — Приложение 1.</p>
<h2>3. Особые условия</h2>
<ul>{% for c in t.conditions %}<li>{{ c }}</li>{% else %}<li>Нет</li>{% endfor %}</ul>
{% if t.guarantor %}<p>Исполнение обязательств обеспечивается поручительством: {{ t.guarantor.full_name }}, ИНН {{ t.guarantor.inn }}.</p>{% endif %}
<h2>Приложение 1. График платежей (первые 12 месяцев)</h2>
<table><tr><th>№</th><th>Дата</th><th>Платёж</th><th>Основной долг</th><th>Проценты</th><th>Остаток</th></tr>
{% for r in rows[:12] %}<tr><td>{{ r.n }}</td><td>{{ r.date }}</td><td>{{ money(r.payment) }}</td><td>{{ money(r.principal) }}</td><td>{{ money(r.interest) }}</td><td>{{ money(r.balance) }}</td></tr>{% endfor %}
</table>
{% if signature %}<div class="stamp">Подписано простой электронной подписью<br>{{ signature.signer_name }}, {{ signature.signed_at.strftime('%d.%m.%Y %H:%M') }} UTC<br>
<span class="muted">SHA-256: {{ signature.document_hash }}</span></div>{% endif %}
</body></html>""")


def render_contract(terms: dict, rows: list[dict], signature=None) -> str:
    def money(x):
        return f"{float(x):,.2f}".replace(",", " ").replace(".", ",")

    def pct(x):
        return f"{float(x):.2f}".replace(".", ",")
    return CONTRACT_TEMPLATE.render(t=terms, rows=rows, money=money, pct=pct, signature=signature)
