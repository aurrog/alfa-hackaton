"""Построение и валидация скоринговой карты для кредитов малому бизнесу.

Шаги (все воспроизводимы, фиксированный seed):
  1. Генерация синтетической «истории выдач» — заёмщики МСП с известным
     исходом (дефолт 90+ за 12 месяцев) по прозрачному процессу порождения
     данных (DGP). Отдельно — out-of-time выборка с дрейфом.
  2. Биннинг признаков по бизнес-логике (монотонные интервалы), расчёт WOE и IV.
  3. Логистическая регрессия на WOE-признаках.
  4. Перевод коэффициентов в баллы (база 600 баллов при шансах 30:1, PDO = 40).
  5. Калибровка грейдов A–E по PD.
  6. Валидация: Gini/KS на train/test/OOT, калибровка по грейдам
     (биномиальный тест), стабильность (PSI), IV признаков.
  7. Экспорт карты в JSON для бэкенда и отчёта валидации в docs.

Запуск:  python ml/build_scorecard.py
Данные синтетические: модель демонстрирует методологию, а не реальный риск.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261020
BUILD_DATE = "2026-10-20"  # фиксирована, чтобы артефакт был побайтно воспроизводим

BASE_SCORE = 600
BASE_ODDS = 30.0  # шансы good:bad при базовом балле
PDO = 40.0  # points to double the odds
FACTOR = PDO / math.log(2)
OFFSET = BASE_SCORE - FACTOR * math.log(BASE_ODDS)

GRADE_PD_BOUNDS = [  # верхняя граница PD для грейда
    ("A", 0.02, "Минимальный риск"),
    ("B", 0.04, "Низкий риск"),
    ("C", 0.08, "Умеренный риск"),
    ("D", 0.15, "Повышенный риск"),
    ("E", 1.00, "Высокий риск"),
]


# ---------------------------------------------------------------------------
# Описание признаков: интервалы задаются по бизнес-смыслу и проверяются на
# монотонность WOE. Нижняя граница включительно, верхняя — исключительно.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NumFeature:
    name: str
    title: str
    source: str
    unit: str
    bins: list[tuple[float | None, float | None, str]]
    client_hint: str  # подсказка клиенту, что улучшить
    missing_label: str | None = None


@dataclass(frozen=True)
class CatFeature:
    name: str
    title: str
    source: str
    categories: list[tuple[str, str]]
    client_hint: str


FEATURES: list[NumFeature | CatFeature] = [
    NumFeature(
        "business_age_months", "Срок ведения бизнеса", "ЕГРЮЛ / ЕГРИП", "мес.",
        [(None, 6, "менее 6 мес."), (6, 12, "6–12 мес."), (12, 24, "1–2 года"),
         (24, 48, "2–4 года"), (48, 96, "4–8 лет"), (96, None, "более 8 лет")],
        "Срок работы бизнеса со временем повышает оценку; молодому бизнесу помогают поручительство гарантийного фонда или залог.",
    ),
    NumFeature(
        "annual_revenue_mln", "Годовая выручка", "ФНС «Прозрачный бизнес» / обороты по счёту", "млн ₽",
        [(None, 5, "до 5 млн ₽"), (5, 15, "5–15 млн ₽"), (15, 60, "15–60 млн ₽"),
         (60, 200, "60–200 млн ₽"), (200, None, "более 200 млн ₽")],
        "Подтверждённая выручка повышает оценку: проводите выручку через расчётный счёт.",
    ),
    NumFeature(
        "turnover_volatility", "Стабильность оборотов", "Обороты по расчётному счёту (АБС / выписка)", "коэф. вариации",
        [(None, 0.15, "стабильные"), (0.15, 0.30, "умеренные колебания"),
         (0.30, 0.50, "заметные колебания"), (0.50, None, "сильные колебания")],
        "Равномерные поступления на счёт повышают оценку; сезонность можно пояснить в заявке.",
        missing_label="нет данных об оборотах",
    ),
    NumFeature(
        "debt_load", "Долговая нагрузка", "БКИ + параметры заявки", "доля платежей в выручке",
        [(None, 0.05, "до 5% выручки"), (0.05, 0.10, "5–10% выручки"), (0.10, 0.20, "10–20% выручки"),
         (0.20, 0.30, "20–30% выручки"), (0.30, None, "более 30% выручки")],
        "Снизить нагрузку можно, уменьшив сумму, увеличив срок или погасив часть текущих кредитов.",
    ),
    NumFeature(
        "company_max_overdue_days", "Просрочки компании за 24 мес.", "БКИ", "дней",
        [(None, 1, "нет просрочек"), (1, 30, "до 30 дней"), (30, 90, "30–89 дней"), (90, None, "90 дней и более")],
        "Своевременные платежи по текущим кредитам — главный способ улучшить кредитную историю.",
    ),
    NumFeature(
        "owner_max_overdue_days", "Просрочки собственника за 24 мес.", "БКИ (поручитель)", "дней",
        [(None, 1, "нет просрочек"), (1, 30, "до 30 дней"), (30, 90, "30–89 дней"), (90, None, "90 дней и более")],
        "Кредитная история собственника учитывается через поручительство — проверьте её в БКИ.",
    ),
    NumFeature(
        "bki_inquiries_30d", "Запросы кредитной истории за 30 дней", "БКИ", "шт.",
        [(None, 2, "0–1"), (2, 4, "2–3"), (4, 7, "4–6"), (7, None, "7 и более")],
        "Много одновременных заявок в разные банки снижает оценку — подавайте заявки адресно.",
    ),
    NumFeature(
        "tax_arrears_ratio", "Налоговая задолженность", "ФНС «Прозрачный бизнес»", "к месячной выручке",
        [(None, 0.0001, "нет задолженности"), (0.0001, 0.10, "до 10% мес. выручки"), (0.10, None, "более 10% мес. выручки")],
        "Погасите задолженность по налогам и пеням — после обновления данных ФНС оценка вырастет.",
    ),
    CatFeature(
        "industry_risk", "Отраслевой риск (ОКВЭД)", "ЕГРЮЛ / ЕГРИП",
        [("low", "низкий"), ("medium", "средний"), ("high", "повышенный")],
        "Отраслевой риск не зависит от вас; его компенсируют обеспечение и стабильные обороты.",
    ),
    NumFeature(
        "bank_relationship_months", "История обслуживания в банке", "АБС банка", "мес.",
        [(None, 1, "не клиент банка"), (1, 12, "до 1 года"), (12, 36, "1–3 года"), (36, None, "более 3 лет")],
        "Обслуживание расчётного счёта в банке даёт данные об оборотах и повышает оценку.",
    ),
]


# ---------------------------------------------------------------------------
# 1. Синтетические данные
# ---------------------------------------------------------------------------
def generate(n: int, rng: np.random.Generator, drift: bool = False) -> pd.DataFrame:
    z = rng.normal(0, 1, n)  # латентное «качество» бизнеса

    young_share = 0.30 if drift else 0.24
    age = np.where(
        rng.random(n) < young_share,
        rng.uniform(3, 24, n),
        np.exp(rng.normal(math.log(60), 0.7, n)),
    )
    age = np.clip(age, 3, 360)

    revenue = np.exp(rng.normal(math.log(24) + 0.35 * z + 0.25 * np.log1p(age / 24), 1.0, n))
    revenue = np.clip(revenue, 0.6, 2500)

    vol = np.clip(rng.beta(2.2, 7.5, n) + 0.06 * (-z) + 0.10 * (age < 12), 0.03, 1.2)

    dl_mean = 0.11 + (0.03 if drift else 0.0) - 0.02 * z
    debt_load = np.clip(rng.gamma(2.3, dl_mean / 2.3, n), 0.0, 0.85)

    def overdue(shift: float) -> np.ndarray:
        u = rng.random(n)
        t = 1 / (1 + np.exp(-(-1.0 - 0.9 * z + shift)))  # вероятность «плохой» истории
        cls = np.where(u > t, 0, np.where(rng.random(n) < 0.62, 1, np.where(rng.random(n) < 0.68, 2, 3)))
        days = np.select(
            [cls == 0, cls == 1, cls == 2, cls == 3],
            [0, rng.integers(1, 30, n), rng.integers(30, 90, n), rng.integers(90, 400, n)],
        )
        return days

    comp_overdue = overdue(0.0)
    owner_overdue = np.where(rng.random(n) < 0.55, comp_overdue * rng.uniform(0.3, 1.1, n), overdue(-0.3)).astype(int)

    inq = rng.poisson(np.clip(1.0 + 0.6 * (-z) + 4.0 * debt_load + (0.4 if drift else 0), 0.1, None))

    has_arrears = rng.random(n) < 1 / (1 + np.exp(-(-2.1 - 0.8 * z)))
    tax_ratio = np.where(has_arrears, rng.exponential(0.08, n), 0.0)

    industry = rng.choice(["low", "medium", "high"], size=n, p=[0.3, 0.45, 0.25])

    is_client = rng.random(n) < 0.55
    relationship = np.where(is_client, np.minimum(age, rng.uniform(1, 140, n)), 0.0)

    vol_missing = (~is_client) & (rng.random(n) < 0.12)

    # Процесс порождения дефолта (известен только «природе», модель его не видит)
    logit = (
        -3.85
        + 1.15 * np.exp(-age / 20) - 0.30 * np.log1p(age / 60)
        - 0.28 * np.log(revenue / 20)
        + 1.9 * (vol - 0.2)
        + 4.2 * (debt_load - 0.12) + 3.0 * np.maximum(0, debt_load - 0.30)
        + np.select([comp_overdue == 0, comp_overdue < 30, comp_overdue < 90], [0, 0.55, 1.35], 2.4)
        + np.select([owner_overdue == 0, owner_overdue < 30, owner_overdue < 90], [0, 0.35, 0.95], 1.7)
        + 0.16 * inq
        + np.where(tax_ratio > 0, 0.65 + 1.4 * np.minimum(tax_ratio, 1.0), 0)
        + np.select([industry == "low", industry == "medium"], [-0.30, 0.0], 0.45)
        + np.where(is_client, -0.25 - 0.004 * relationship, 0)
        - 0.35 * z
        + rng.normal(0, 0.45, n)
    )
    p = 1 / (1 + np.exp(-logit))
    default = (rng.random(n) < p).astype(int)

    df = pd.DataFrame(
        {
            "business_age_months": age.round(0),
            "annual_revenue_mln": revenue.round(2),
            "turnover_volatility": np.where(vol_missing, np.nan, vol.round(3)),
            "debt_load": debt_load.round(4),
            "company_max_overdue_days": comp_overdue,
            "owner_max_overdue_days": owner_overdue,
            "bki_inquiries_30d": inq,
            "tax_arrears_ratio": tax_ratio.round(4),
            "industry_risk": industry,
            "bank_relationship_months": relationship.round(0),
            "default_12m": default,
        }
    )
    return df


# ---------------------------------------------------------------------------
# 2. Биннинг и WOE
# ---------------------------------------------------------------------------
MISSING = "__missing__"


def bin_labels(f: NumFeature | CatFeature) -> list[str]:
    if isinstance(f, CatFeature):
        return [c for c, _ in f.categories]
    labels = [lbl for _, _, lbl in f.bins]
    if f.missing_label:
        labels.append(MISSING)
    return labels


def assign_bin(f: NumFeature | CatFeature, values: pd.Series) -> pd.Series:
    if isinstance(f, CatFeature):
        return values.astype(str)
    out = pd.Series(index=values.index, dtype=object)
    for lo, hi, lbl in f.bins:
        mask = pd.Series(True, index=values.index)
        if lo is not None:
            mask &= values >= lo
        if hi is not None:
            mask &= values < hi
        out[mask & values.notna()] = lbl
    out[values.isna()] = MISSING
    return out


def woe_table(f: NumFeature | CatFeature, bins: pd.Series, y: pd.Series) -> pd.DataFrame:
    total_good = (y == 0).sum()
    total_bad = (y == 1).sum()
    rows = []
    for lbl in bin_labels(f):
        m = bins == lbl
        good = int(((y == 0) & m).sum())
        bad = int(((y == 1) & m).sum())
        dg = (good + 0.5) / (total_good + 0.5)
        db = (bad + 0.5) / (total_bad + 0.5)
        woe = math.log(dg / db)
        rows.append({"bin": lbl, "count": good + bad, "bad": bad, "bad_rate": bad / max(good + bad, 1),
                     "woe": woe, "iv": (dg - db) * woe})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3–5. Обучение и баллы
# ---------------------------------------------------------------------------
def to_woe(df: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = {}
    for f in FEATURES:
        b = assign_bin(f, df[f.name])
        mapping = dict(zip(tables[f.name]["bin"], tables[f.name]["woe"]))
        out[f.name] = b.map(mapping).astype(float)
    return pd.DataFrame(out, index=df.index)


def score_from_points(points_df: pd.DataFrame) -> pd.Series:
    return points_df.sum(axis=1)


def pd_from_score(score: np.ndarray | float) -> np.ndarray | float:
    log_odds_good = (np.asarray(score) - OFFSET) / FACTOR
    return 1 / (1 + np.exp(log_odds_good))


def score_from_pd(p: float) -> float:
    return OFFSET + FACTOR * math.log((1 - p) / p)


def gini(y, s) -> float:
    return 2 * roc_auc_score(y, s) - 1


def ks_stat(y, s) -> float:
    fpr, tpr, _ = roc_curve(y, s)
    return float(np.max(np.abs(tpr - fpr)))


def psi(expected: np.ndarray, actual: np.ndarray, edges: np.ndarray) -> float:
    e, _ = np.histogram(expected, edges)
    a, _ = np.histogram(actual, edges)
    e = np.clip(e / e.sum(), 1e-6, None)
    a = np.clip(a / a.sum(), 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def grade_of(p: float) -> str:
    for g, ub, _ in GRADE_PD_BOUNDS:
        if p < ub:
            return g
    return "E"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24000)
    ap.add_argument("--n-oot", type=int, default=6000)
    ap.add_argument("--out", default=str(ROOT / "backend/app/domain/scoring/scorecard.json"))
    ap.add_argument("--report", default=str(ROOT / "docs/03-decision"))
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    dev = generate(args.n, rng)
    oot = generate(args.n_oot, rng, drift=True)
    data_dir = ROOT / "ml/data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dev.to_csv(data_dir / "synthetic_dev.csv", index=False)
    oot.to_csv(data_dir / "synthetic_oot.csv", index=False)

    train, test = train_test_split(dev, test_size=0.3, random_state=SEED, stratify=dev["default_12m"])
    y_tr, y_te, y_oot = train["default_12m"], test["default_12m"], oot["default_12m"]

    tables = {f.name: woe_table(f, assign_bin(f, train[f.name]), y_tr) for f in FEATURES}

    X_tr = to_woe(train, tables)
    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(X_tr, y_tr)
    beta = dict(zip(X_tr.columns, model.coef_[0]))
    alpha = float(model.intercept_[0])
    n_feat = len(FEATURES)

    # Баллы: logit(bad) = alpha + Σ beta_i·WOE_i  →  ln(odds_good) = -(alpha + Σ beta_i·WOE_i)
    # score = offset + factor·ln(odds_good) раскладывается по признакам:
    # points_ij = -(beta_i·WOE_ij + alpha/n)·factor + offset/n
    feature_specs = []
    points_map: dict[str, dict[str, int]] = {}
    for f in FEATURES:
        t = tables[f.name]
        pts = {}
        bins_out = []
        for _, row in t.iterrows():
            p = -(beta[f.name] * row["woe"] + alpha / n_feat) * FACTOR + OFFSET / n_feat
            pts[row["bin"]] = int(round(p))
        points_map[f.name] = pts
        max_pts = max(pts.values())
        if isinstance(f, CatFeature):
            for code, label in f.categories:
                r = t[t["bin"] == code].iloc[0]
                bins_out.append({"value": code, "label": label, "points": pts[code], "woe": round(float(r["woe"]), 4),
                                 "bad_rate": round(float(r["bad_rate"]), 4), "share": round(float(r["count"] / len(train)), 4)})
            spec = {"name": f.name, "title": f.title, "source": f.source, "type": "categorical",
                    "bins": bins_out, "max_points": max_pts, "client_hint": f.client_hint,
                    "beta": round(float(beta[f.name]), 5), "iv": round(float(t["iv"].sum()), 4)}
        else:
            for lo, hi, lbl in f.bins:
                r = t[t["bin"] == lbl].iloc[0]
                bins_out.append({"lower": lo, "upper": hi, "label": lbl, "points": pts[lbl],
                                 "woe": round(float(r["woe"]), 4), "bad_rate": round(float(r["bad_rate"]), 4),
                                 "share": round(float(r["count"] / len(train)), 4)})
            missing = None
            if f.missing_label:
                r = t[t["bin"] == MISSING].iloc[0]
                missing = {"label": f.missing_label, "points": pts[MISSING], "woe": round(float(r["woe"]), 4),
                           "bad_rate": round(float(r["bad_rate"]), 4), "share": round(float(r["count"] / len(train)), 4)}
            spec = {"name": f.name, "title": f.title, "source": f.source, "type": "numeric", "unit": f.unit,
                    "bins": bins_out, "missing": missing, "max_points": max_pts, "client_hint": f.client_hint,
                    "beta": round(float(beta[f.name]), 5), "iv": round(float(t["iv"].sum()), 4)}
        feature_specs.append(spec)

    def points_df(df: pd.DataFrame) -> pd.DataFrame:
        cols = {}
        for f in FEATURES:
            b = assign_bin(f, df[f.name])
            cols[f.name] = b.map(points_map[f.name]).astype(float)
        return pd.DataFrame(cols, index=df.index)

    s_tr = score_from_points(points_df(train)).to_numpy()
    s_te = score_from_points(points_df(test)).to_numpy()
    s_oot = score_from_points(points_df(oot)).to_numpy()

    # Gini считаем по «плохости»: чем ниже балл, тем выше риск → используем -score
    metrics = {
        "gini_train": round(gini(y_tr, -s_tr), 4),
        "gini_test": round(gini(y_te, -s_te), 4),
        "gini_oot": round(gini(y_oot, -s_oot), 4),
        "ks_test": round(ks_stat(y_te, -s_te), 4),
        "ks_oot": round(ks_stat(y_oot, -s_oot), 4),
        "default_rate_train": round(float(y_tr.mean()), 4),
        "default_rate_test": round(float(y_te.mean()), 4),
        "default_rate_oot": round(float(y_oot.mean()), 4),
        "n_train": int(len(train)), "n_test": int(len(test)), "n_oot": int(len(oot)),
    }
    edges = np.quantile(s_tr, np.linspace(0, 1, 11))
    edges[0], edges[-1] = -1e9, 1e9
    metrics["psi_score_test"] = round(psi(s_tr, s_te, edges), 4)
    metrics["psi_score_oot"] = round(psi(s_tr, s_oot, edges), 4)

    grades = []
    lower_pd = 0.0
    for g, ub, title in GRADE_PD_BOUNDS:
        min_score = score_from_pd(ub) if ub < 1 else None
        grades.append({"grade": g, "title": title, "pd_from": lower_pd, "pd_to": ub,
                       "min_score": round(min_score, 1) if min_score is not None else None})
        lower_pd = ub

    def calib(scores: np.ndarray, y: pd.Series) -> list[dict]:
        rows = []
        pds = pd_from_score(scores)
        gr = np.array([grade_of(p) for p in pds])
        for g, _, _ in GRADE_PD_BOUNDS:
            m = gr == g
            n = int(m.sum())
            if n == 0:
                rows.append({"grade": g, "n": 0})
                continue
            obs = float(y.to_numpy()[m].mean())
            exp = float(pds[m].mean())
            k = int(y.to_numpy()[m].sum())
            # двусторонний биномиальный тест: согласуется ли наблюдаемая доля дефолтов с прогнозной
            pval = float(stats.binomtest(k, n, exp).pvalue)
            rows.append({"grade": g, "n": n, "share": round(n / len(y), 4), "pd_expected": round(exp, 4),
                         "dr_observed": round(obs, 4), "binom_p_value": round(pval, 4)})
        return rows

    calibration = {"test": calib(s_te, y_te), "oot": calib(s_oot, y_oot)}

    # PSI по признакам (стабильность входов)
    feat_psi = {}
    for f in FEATURES:
        b_tr = assign_bin(f, train[f.name]).value_counts(normalize=True)
        b_oot = assign_bin(f, oot[f.name]).value_counts(normalize=True)
        idx = sorted(set(b_tr.index) | set(b_oot.index))
        e = np.clip(np.array([b_tr.get(i, 0) for i in idx]), 1e-6, None)
        a = np.clip(np.array([b_oot.get(i, 0) for i in idx]), 1e-6, None)
        feat_psi[f.name] = round(float(np.sum((a - e) * np.log(a / e))), 4)

    scorecard = {
        "model_id": "sme-scorecard",
        "version": "1.0.0",
        "built_at": BUILD_DATE,
        "description": "Скоринговая карта (логистическая регрессия на WOE) для кредитов МСП. Обучена на синтетических данных.",
        "target": "Дефолт 90+ дней в течение 12 месяцев после выдачи",
        "scaling": {"base_score": BASE_SCORE, "base_odds": BASE_ODDS, "pdo": PDO,
                    "factor": round(FACTOR, 6), "offset": round(OFFSET, 6)},
        "features": feature_specs,
        "grades": grades,
        "metrics": metrics,
        "calibration": calibration,
        "feature_psi_oot": feat_psi,
        "intercept": round(alpha, 6),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---------------- Графики и отчёт ----------------
    report_dir = Path(args.report)
    img = report_dir / "img"
    img.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.dpi": 110, "svg.hashsalt": "scorecard"})

    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    for name, y, s in [("train", y_tr, s_tr), ("test", y_te, s_te), ("OOT", y_oot, s_oot)]:
        fpr, tpr, _ = roc_curve(y, -s)
        ax.plot(fpr, tpr, label=f"{name}: Gini {gini(y, -s):.2f}")
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    ax.set_xlabel("Доля хороших, отнесённых к плохим (FPR)")
    ax.set_ylabel("Доля выявленных плохих (TPR)")
    ax.set_title("ROC-кривая скоринговой карты")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(img / "roc.png", metadata={"Software": None})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    bins_hist = np.linspace(min(s_te.min(), s_oot.min()) - 5, max(s_te.max(), s_oot.max()) + 5, 40)
    ax.hist(s_te[y_te.to_numpy() == 0], bins=bins_hist, alpha=0.6, density=True, label="без дефолта")
    ax.hist(s_te[y_te.to_numpy() == 1], bins=bins_hist, alpha=0.6, density=True, label="дефолт")
    for g in grades:
        if g["min_score"]:
            ax.axvline(g["min_score"], color="black", lw=0.6, ls=":")
            ax.text(g["min_score"] + 2, ax.get_ylim()[1] * 0.92, g["grade"], fontsize=9)
    ax.set_xlabel("Скоринговый балл")
    ax.set_title("Распределение баллов (test) и границы грейдов")
    ax.legend()
    fig.tight_layout()
    fig.savefig(img / "score_distribution.png", metadata={"Software": None})
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.0, 3.8))
    cal = [r for r in calibration["test"] if r.get("n")]
    x = np.arange(len(cal))
    ax.bar(x - 0.18, [r["pd_expected"] * 100 for r in cal], 0.36, label="прогноз PD")
    ax.bar(x + 0.18, [r["dr_observed"] * 100 for r in cal], 0.36, label="факт DR")
    ax.set_xticks(x, [r["grade"] for r in cal])
    ax.set_ylabel("%")
    ax.set_title("Калибровка по грейдам (test)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(img / "calibration.png", metadata={"Software": None})
    plt.close(fig)

    def pc(v: float, d: int = 1) -> str:
        return f"{v * 100:.{d}f}%".replace(".", ",")

    def num(v: float, d: int = 3) -> str:
        return f"{v:.{d}f}".replace(".", ",")

    lines = []
    lines.append("# Отчёт о построении и валидации скоринговой карты\n")
    lines.append("> Файл сгенерирован скриптом `ml/build_scorecard.py` (seed фиксирован, результат воспроизводим). "
                 "Данные синтетические: отчёт демонстрирует методологию проверки модели, а не реальный кредитный риск.\n")
    lines.append(f"Версия модели: **{scorecard['model_id']} {scorecard['version']}**. Целевое событие: {scorecard['target']}.\n")
    lines.append("## Выборки\n")
    lines.append("| Выборка | Наблюдений | Доля дефолтов |\n|---|---|---|")
    lines.append(f"| Обучающая (train) | {metrics['n_train']} | {pc(metrics['default_rate_train'])} |")
    lines.append(f"| Тестовая (test) | {metrics['n_test']} | {pc(metrics['default_rate_test'])} |")
    lines.append(f"| Out-of-time (OOT, с дрейфом: выше нагрузка, больше молодых компаний) | {metrics['n_oot']} | {pc(metrics['default_rate_oot'])} |\n")
    lines.append("## Дискриминирующая способность\n")
    lines.append("| Метрика | train | test | OOT | Ориентир |\n|---|---|---|---|---|")
    lines.append(f"| Gini | {num(metrics['gini_train'])} | {num(metrics['gini_test'])} | {num(metrics['gini_oot'])} | > 0,40 приемлемо, > 0,60 хорошо |")
    lines.append(f"| KS | — | {num(metrics['ks_test'])} | {num(metrics['ks_oot'])} | > 0,30 |\n")
    lines.append("![ROC](img/roc.png)\n")
    lines.append("## Стабильность (PSI)\n")
    lines.append(f"PSI распределения баллов: test — **{num(metrics['psi_score_test'])}**, OOT — **{num(metrics['psi_score_oot'])}** "
                 "(< 0,10 — стабильно, 0,10–0,25 — умеренный сдвиг, требует наблюдения, > 0,25 — значимый сдвиг, нужна перекалибровка).\n")
    lines.append("| Признак | PSI (OOT к train) |\n|---|---|")
    for f in FEATURES:
        lines.append(f"| {f.title} | {num(feat_psi[f.name])} |")
    lines.append("\n## Калибровка по грейдам\n")
    for sample in ("test", "oot"):
        lines.append(f"**{sample.upper()}**\n")
        lines.append("| Грейд | Наблюдений | Доля | Прогноз PD | Факт DR | p-value биномиального теста |\n|---|---|---|---|---|---|")
        for r in calibration[sample]:
            if not r.get("n"):
                lines.append(f"| {r['grade']} | 0 | — | — | — | — |")
                continue
            lines.append(f"| {r['grade']} | {r['n']} | {pc(r['share'])} | {pc(r['pd_expected'], 2)} | {pc(r['dr_observed'], 2)} | {num(r['binom_p_value'])} |")
        lines.append("")
    lines.append("![Калибровка](img/calibration.png)\n")
    lines.append("![Распределение баллов](img/score_distribution.png)\n")
    lines.append("## Информационная ценность признаков (IV)\n")
    lines.append("| Признак | Источник | IV | Коэффициент β |\n|---|---|---|---|")
    for s in sorted(feature_specs, key=lambda x: -x["iv"]):
        lines.append(f"| {s['title']} | {s['source']} | {num(s['iv'])} | {num(s['beta'])} |")
    lines.append("\nIV: < 0,02 — бесполезный, 0,02–0,1 — слабый, 0,1–0,3 — средний, > 0,3 — сильный признак.\n")
    lines.append("## Баллы скоринговой карты\n")
    lines.append(f"Шкала: {BASE_SCORE} баллов соответствуют шансам {BASE_ODDS:.0f}:1 (good:bad), каждые {PDO:.0f} баллов удваивают шансы.\n")
    for s in feature_specs:
        lines.append(f"**{s['title']}** ({s['source']})\n")
        lines.append("| Интервал | Баллы | Доля дефолтов в интервале | Доля выборки |\n|---|---|---|---|")
        for b in s["bins"]:
            lines.append(f"| {b['label']} | {b['points']} | {pc(b['bad_rate'])} | {pc(b['share'])} |")
        if s.get("missing"):
            m = s["missing"]
            lines.append(f"| {m['label']} | {m['points']} | {pc(m['bad_rate'])} | {pc(m['share'])} |")
        lines.append("")
    lines.append("## Грейды\n")
    lines.append("| Грейд | Описание | PD | Минимальный балл |\n|---|---|---|---|")
    for g in grades:
        ms = f"{g['min_score']:.0f}" if g["min_score"] else "—"
        lines.append(f"| {g['grade']} | {g['title']} | {pc(g['pd_from'], 0)}–{pc(g['pd_to'], 0)} | {ms} |")
    lines.append("")
    (report_dir / "scorecard-validation.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("PSI by feature:", feat_psi)
    for s in feature_specs:
        print(s["name"], [b["points"] for b in s["bins"]], (s.get("missing") or {}).get("points"))
    print("grades:", grades)


if __name__ == "__main__":
    main()
