"""Применение скоринговой карты.

Карта строится и валидируется офлайн (`ml/build_scorecard.py`) и попадает сюда
как версионированный JSON-артефакт. Сервис только применяет её: это быстро,
детерминированно и полностью объяснимо — по каждому фактору видно, сколько
баллов он дал и сколько баллов «потеряно» относительно лучшего значения.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.domain.okved import sector_by_okved

DEFAULT_PATH = Path(__file__).with_name("scorecard.json")


@dataclass
class FeatureInputs:
    registration_date: date | None
    annual_revenue: float | None  # ₽ за год (подтверждённая: ФНС / обороты)
    turnover_volatility: float | None  # коэффициент вариации месячных поступлений
    existing_monthly_payments: float  # ₽/мес по действующим кредитам (БКИ)
    new_loan_payment: float  # ₽/мес по запрашиваемому кредиту
    company_max_overdue_days: int | None
    owner_max_overdue_days: int | None
    bki_inquiries_30d: int | None
    tax_arrears: float  # ₽
    okved_code: str | None
    bank_relationship_months: int
    today: date | None = None


def compute_features(x: FeatureInputs) -> dict[str, float | str | None]:
    today = x.today or date.today()
    age = None
    if x.registration_date:
        age = (today.year - x.registration_date.year) * 12 + today.month - x.registration_date.month
        age = max(age, 0)
    monthly_revenue = (x.annual_revenue / 12) if x.annual_revenue else None
    debt_load = None
    if monthly_revenue and monthly_revenue > 0:
        debt_load = (x.existing_monthly_payments + x.new_loan_payment) / monthly_revenue
    tax_ratio = None
    if monthly_revenue and monthly_revenue > 0:
        tax_ratio = x.tax_arrears / monthly_revenue
    elif x.tax_arrears == 0:
        tax_ratio = 0.0
    return {
        "business_age_months": age,
        "annual_revenue_mln": round(x.annual_revenue / 1_000_000, 3) if x.annual_revenue else None,
        "turnover_volatility": x.turnover_volatility,
        "debt_load": round(debt_load, 4) if debt_load is not None else None,
        "company_max_overdue_days": x.company_max_overdue_days,
        "owner_max_overdue_days": x.owner_max_overdue_days,
        "bki_inquiries_30d": x.bki_inquiries_30d,
        "tax_arrears_ratio": round(tax_ratio, 4) if tax_ratio is not None else None,
        "industry_risk": sector_by_okved(x.okved_code).risk,
        "bank_relationship_months": x.bank_relationship_months,
    }


@dataclass
class FactorResult:
    name: str
    title: str
    source: str
    value: float | str | None
    display_value: str
    bin_label: str
    points: int
    max_points: int
    lost_points: int
    client_hint: str
    missing: bool = False


@dataclass
class ScoreResult:
    model_id: str
    model_version: str
    score: int
    pd: float
    grade: str
    grade_title: str
    factors: list[FactorResult] = field(default_factory=list)
    incomplete: bool = False

    def negatives(self, n: int = 3) -> list[FactorResult]:
        return [f for f in sorted(self.factors, key=lambda f: -f.lost_points) if f.lost_points >= 10][:n]

    def positives(self, n: int = 3) -> list[FactorResult]:
        return [f for f in sorted(self.factors, key=lambda f: (f.lost_points, -f.points)) if f.lost_points <= 5 and not f.missing][:n]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["pd"] = round(self.pd, 5)
        return d


def _fmt(name: str, v: float | str | None) -> str:
    if v is None:
        return "нет данных"
    if name == "industry_risk":
        return {"low": "низкий", "medium": "средний", "high": "повышенный"}.get(str(v), str(v))
    if name in ("debt_load", "tax_arrears_ratio"):
        return f"{float(v) * 100:.1f}%".replace(".", ",")
    if name == "turnover_volatility":
        return f"{float(v):.2f}".replace(".", ",")
    if name == "annual_revenue_mln":
        return f"{float(v):.1f} млн ₽".replace(".", ",")
    if name in ("business_age_months", "bank_relationship_months"):
        m = int(v)
        return f"{m // 12} г. {m % 12} мес." if m >= 12 else f"{m} мес."
    if name.endswith("overdue_days"):
        return "нет" if int(v) == 0 else f"{int(v)} дн."
    return str(v)


class Scorecard:
    def __init__(self, spec: dict):
        self.spec = spec
        self.model_id = spec["model_id"]
        self.version = spec["version"]
        self.scaling = spec["scaling"]
        self.grades = spec["grades"]

    def pd_from_score(self, score: float) -> float:
        log_odds_good = (score - self.scaling["offset"]) / self.scaling["factor"]
        return 1 / (1 + math.exp(log_odds_good))

    def grade_from_pd(self, p: float) -> tuple[str, str]:
        for g in self.grades:
            if p < g["pd_to"]:
                return g["grade"], g["title"]
        return self.grades[-1]["grade"], self.grades[-1]["title"]

    def _bin(self, f: dict, value) -> tuple[str, int, bool]:
        if f["type"] == "categorical":
            for b in f["bins"]:
                if b["value"] == value:
                    return b["label"], b["points"], False
            worst = min(f["bins"], key=lambda b: b["points"])
            return worst["label"], worst["points"], True
        if value is None:
            if f.get("missing"):
                return f["missing"]["label"], f["missing"]["points"], True
            worst = min(f["bins"], key=lambda b: b["points"])  # консервативно: худший интервал
            return "нет данных", worst["points"], True
        for b in f["bins"]:
            lo, hi = b["lower"], b["upper"]
            if (lo is None or value >= lo) and (hi is None or value < hi):
                return b["label"], b["points"], False
        raise ValueError(f"value {value} out of bins for {f['name']}")

    def score(self, features: dict) -> ScoreResult:
        factors: list[FactorResult] = []
        total = 0
        incomplete = False
        for f in self.spec["features"]:
            v = features.get(f["name"])
            label, pts, missing = self._bin(f, v)
            incomplete |= missing and not (f.get("missing") and v is None)
            total += pts
            factors.append(FactorResult(
                name=f["name"], title=f["title"], source=f["source"], value=v, display_value=_fmt(f["name"], v),
                bin_label=label, points=pts, max_points=f["max_points"], lost_points=f["max_points"] - pts,
                client_hint=f["client_hint"], missing=missing,
            ))
        p = self.pd_from_score(total)
        grade, title = self.grade_from_pd(p)
        return ScoreResult(self.model_id, self.version, int(total), p, grade, title, factors, incomplete)


@lru_cache(maxsize=4)
def load_scorecard(path: str | None = None) -> Scorecard:
    p = Path(path) if path else DEFAULT_PATH
    return Scorecard(json.loads(p.read_text(encoding="utf-8")))
