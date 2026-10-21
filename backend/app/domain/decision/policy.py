"""Кредитная политика — параметры, по которым принимается решение.

Политика хранится в БД версиями (таблица credit_policies). Каждое решение
ссылается на версию политики и версию скоринговой модели, поэтому любое решение
можно воспроизвести и объяснить. Здесь — значения по умолчанию (версия 1)
и описание редактируемых параметров для экрана «Кредитная политика».
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

DEFAULT_POLICY: dict[str, Any] = {
    "key_rate": 14.0,
    "auto_approve_max_amount": 5_000_000,
    "auto_approve_grades": ["A", "B"],
    "manual_grades": ["C", "D"],
    "decline_grades": ["E"],
    "committee_grades": ["D"],
    "grade_premium": {"A": 0.0, "B": 1.5, "C": 3.0, "D": 5.0, "E": 8.0},
    "discount_bank_client": 0.5,
    "discount_secured": 1.0,
    "min_dscr": 1.3,
    "margin_multiplier": 1.0,
    "hard_stop_overdue_days": 90,
    "warn_overdue_days": 30,
    "tax_arrears_stop_amount": 300_000,
    "tax_arrears_stop_ratio": 0.10,
    "turnover_deviation_manual": 0.40,
    "authority_limits": {"analyst": 15_000_000, "senior_analyst": 30_000_000},
    "counter_offer_min_share": 0.3,
    "round_step": 50_000,
    "collateral_ltv": {"real_estate": 0.7, "equipment": 0.5, "vehicle": 0.6, "goods": 0.4, "guarantee_fund": 0.5},
    "covenant_turnover_share": 0.5,
    "offer_validity_days": 10,
    "info_request_days": 14,
}

# Параметры, которые владелец продукта может менять из интерфейса без релиза
EDITABLE: list[dict[str, Any]] = [
    {"key": "key_rate", "title": "Ключевая ставка Банка России, %", "type": "percent", "min": 0, "max": 40, "step": 0.25},
    {"key": "auto_approve_max_amount", "title": "Лимит автоматического решения, ₽", "type": "money", "min": 0, "max": 50_000_000, "step": 500_000},
    {"key": "min_dscr", "title": "Минимальный DSCR (покрытие платежей денежным потоком)", "type": "number", "min": 1.0, "max": 3.0, "step": 0.05},
    {"key": "margin_multiplier", "title": "Коэффициент к отраслевой маржинальности", "type": "number", "min": 0.5, "max": 1.5, "step": 0.05},
    {"key": "grade_premium.B", "title": "Надбавка к ставке, грейд B, п.п.", "type": "percent", "min": 0, "max": 15, "step": 0.25},
    {"key": "grade_premium.C", "title": "Надбавка к ставке, грейд C, п.п.", "type": "percent", "min": 0, "max": 15, "step": 0.25},
    {"key": "grade_premium.D", "title": "Надбавка к ставке, грейд D, п.п.", "type": "percent", "min": 0, "max": 20, "step": 0.25},
    {"key": "authority_limits.analyst", "title": "Полномочия аналитика, ₽", "type": "money", "min": 0, "max": 100_000_000, "step": 1_000_000},
    {"key": "authority_limits.senior_analyst", "title": "Полномочия старшего аналитика, ₽", "type": "money", "min": 0, "max": 200_000_000, "step": 1_000_000},
    {"key": "tax_arrears_stop_amount", "title": "Налоговая задолженность — стоп-фактор от, ₽", "type": "money", "min": 0, "max": 5_000_000, "step": 50_000},
    {"key": "offer_validity_days", "title": "Срок действия предложения, дней", "type": "int", "min": 1, "max": 60, "step": 1},
]


def get_path(d: dict, path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        cur = cur[part]
    return cur


def set_path(d: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = d
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


@dataclass
class Policy:
    version: int
    config: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.config.get(key, DEFAULT_POLICY.get(key))

    @classmethod
    def default(cls) -> Policy:
        return cls(1, copy.deepcopy(DEFAULT_POLICY))

    def with_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {e["key"]: e for e in EDITABLE}
        cfg = copy.deepcopy(self.config)
        for k, v in changes.items():
            if k not in allowed:
                raise ValueError(f"Параметр {k} нельзя менять из интерфейса")
            meta = allowed[k]
            v = float(v) if meta["type"] in ("percent", "number", "money") else int(v)
            if not (meta["min"] <= v <= meta["max"]):
                raise ValueError(f"{meta['title']}: значение вне диапазона {meta['min']}–{meta['max']}")
            if meta["type"] in ("money", "int"):
                v = int(v)
            set_path(cfg, k, v)
        return cfg
