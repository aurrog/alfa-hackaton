"""Кредитный калькулятор: аннуитет, график платежей, обратные расчёты.

Деньги считаются в Decimal с округлением до копеек (ROUND_HALF_UP),
чтобы график сходился до копейки, как в АБС.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(x: float | Decimal | int) -> Decimal:
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def annuity_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    if months <= 0:
        raise ValueError("months must be positive")
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def max_principal(payment: float, annual_rate_pct: float, months: int) -> float:
    """Какую сумму можно взять при заданном ежемесячном платеже."""
    if payment <= 0 or months <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return payment * months
    return payment * (1 - (1 + r) ** -months) / r


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    days_in_month = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, days_in_month))


@dataclass
class ScheduleRow:
    n: int
    date: date
    payment: Decimal
    principal: Decimal
    interest: Decimal
    balance: Decimal

    def as_dict(self) -> dict:
        return {
            "n": self.n, "date": self.date.isoformat(), "payment": float(self.payment),
            "principal": float(self.principal), "interest": float(self.interest), "balance": float(self.balance),
        }


def schedule(principal: float, annual_rate_pct: float, months: int, start: date) -> list[ScheduleRow]:
    """Аннуитетный график. Последний платёж корректируется на остаток."""
    p = money(principal)
    r = Decimal(str(annual_rate_pct)) / Decimal(1200)
    pay = money(annuity_payment(float(p), annual_rate_pct, months))
    balance = p
    rows: list[ScheduleRow] = []
    for i in range(1, months + 1):
        interest = money(balance * r)
        principal_part = pay - interest
        if i == months or principal_part > balance:
            principal_part = balance
            payment = principal_part + interest
        else:
            payment = pay
        balance = money(balance - principal_part)
        rows.append(ScheduleRow(i, add_months(start, i), money(payment), money(principal_part), interest, balance))
    return rows


def loan_summary(principal: float, annual_rate_pct: float, months: int) -> dict:
    pay = annuity_payment(principal, annual_rate_pct, months)
    total = pay * months
    return {
        "monthly_payment": round(pay, 2),
        "total_payment": round(total, 2),
        "overpayment": round(total - principal, 2),
        "effective_rate": round(effective_annual_rate(annual_rate_pct), 3),
    }


def effective_annual_rate(annual_rate_pct: float) -> float:
    """Эффективная годовая ставка при ежемесячной капитализации (ориентир для ПСК без комиссий)."""
    r = annual_rate_pct / 100 / 12
    return (math.pow(1 + r, 12) - 1) * 100


def round_down(amount: float, step: int = 50_000) -> float:
    return math.floor(amount / step) * step
