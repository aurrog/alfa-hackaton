"""Общие функции симулятора: реквизиты, детерминированный генератор случайных чисел, даты."""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

_INN10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN12_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _ctrl(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(inn: str) -> bool:
    if not inn or not inn.isdigit() or len(inn) not in (10, 12):
        return False
    d = [int(c) for c in inn]
    if len(inn) == 10:
        return _ctrl(d, _INN10) == d[9]
    return _ctrl(d, _INN12_1) == d[10] and _ctrl(d, _INN12_2) == d[11]


def make_person_inn(rng: random.Random, region: str = "77") -> str:
    d = [int(c) for c in region[:2].rjust(2, "7")] + [rng.randint(0, 9) for _ in range(8)]
    d.append(_ctrl(d, _INN12_1))
    d.append(_ctrl(d, _INN12_2))
    return "".join(map(str, d))


def make_ogrn(inn: str, reg: date) -> str:
    """ОГРН (13) для юрлица или ОГРНИП (15) для ИП с корректным контрольным разрядом."""
    rng = rng_for(inn, "ogrn")
    yy = f"{reg.year % 100:02d}"
    if len(inn) == 10:
        body = "1" + yy + inn[:2] + "".join(str(rng.randint(0, 9)) for _ in range(7))
        return body + str(int(body) % 11 % 10)
    body = "3" + yy + inn[:2] + "".join(str(rng.randint(0, 9)) for _ in range(9))
    return body + str(int(body) % 13 % 10)


def rng_for(inn: str, salt: str = "") -> random.Random:
    seed = int(hashlib.sha256(f"{inn}:{salt}".encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def months_ago(n: int, today: date | None = None) -> date:
    today = today or date.today()
    y, m = divmod(today.month - 1 - n, 12)
    year, month = today.year + y, m + 1
    return date(year, month, min(today.day, 28))


def days_ago(n: int, today: date | None = None) -> date:
    return (today or date.today()) - timedelta(days=n)


def last_months(n: int, today: date | None = None) -> list[str]:
    """Последние n полных месяцев в формате YYYY-MM (от старого к новому)."""
    today = today or date.today()
    out = []
    for i in range(n, 0, -1):
        d = months_ago(i, today)
        out.append(f"{d.year:04d}-{d.month:02d}")
    return out


def series(rng: random.Random, avg: float, cv: float, n: int, trend: float = 0.0, seasonal: float = 0.0) -> list[float]:
    """Ряд месячных поступлений со средним avg и коэффициентом вариации ≈ cv."""
    vals = []
    for i in range(n):
        t = (i - (n - 1) / 2) / max(n - 1, 1)
        base = avg * (1 + trend * t + seasonal * (0.5 if i % 12 in (10, 11) else 0))
        vals.append(max(base * (1 + rng.gauss(0, cv)), avg * 0.05))
    k = avg / (sum(vals) / n)
    return [round(v * k, 2) for v in vals]
