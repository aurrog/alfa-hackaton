"""Справочник отраслей по ОКВЭД: отраслевой риск, типичная маржинальность,
приоритетность для программы господдержки и тема для персональной ленты.

Значения синтетические и упрощённые — для демонстрации логики.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sector:
    key: str
    name: str
    risk: str  # low | medium | high — признак скоринговой карты
    margin: float  # типичная доля операционного денежного потока в выручке
    gov_priority: bool  # приоритетная отрасль программы кредитования по ключевой ставке
    topic: str  # тег ленты


SECTORS: dict[str, Sector] = {
    "agro": Sector("agro", "Сельское хозяйство", "medium", 0.13, False, "agro"),
    "manufacturing": Sector("manufacturing", "Обрабатывающие производства", "medium", 0.11, True, "manufacturing"),
    "construction": Sector("construction", "Строительство", "high", 0.10, False, "construction"),
    "wholesale": Sector("wholesale", "Оптовая торговля", "medium", 0.06, False, "trade"),
    "retail": Sector("retail", "Розничная торговля", "high", 0.07, False, "trade"),
    "auto": Sector("auto", "Торговля и ремонт автотранспорта", "medium", 0.08, False, "trade"),
    "logistics": Sector("logistics", "Транспорт и логистика", "medium", 0.10, True, "logistics"),
    "hospitality": Sector("hospitality", "Гостиницы и туризм", "medium", 0.14, True, "tourism"),
    "food_service": Sector("food_service", "Общественное питание", "high", 0.12, False, "horeca"),
    "it": Sector("it", "IT и разработка ПО", "low", 0.18, True, "it"),
    "media": Sector("media", "Медиа и креативные индустрии", "medium", 0.14, True, "creative"),
    "real_estate": Sector("real_estate", "Операции с недвижимостью", "medium", 0.20, False, "real_estate"),
    "science": Sector("science", "Научные исследования и инжиниринг", "low", 0.15, True, "science"),
    "professional": Sector("professional", "Профессиональные услуги", "low", 0.16, False, "services"),
    "education": Sector("education", "Образование", "low", 0.15, False, "services"),
    "health": Sector("health", "Здравоохранение", "low", 0.16, False, "services"),
    "creative": Sector("creative", "Культура, искусство, развлечения", "medium", 0.13, True, "creative"),
    "services": Sector("services", "Бытовые и персональные услуги", "medium", 0.13, False, "services"),
    "other": Sector("other", "Прочие виды деятельности", "medium", 0.10, False, "general"),
}

# (начало кода, конец кода включительно) → сектор по первым двум цифрам ОКВЭД
_RANGES: list[tuple[int, int, str]] = [
    (1, 3, "agro"), (10, 33, "manufacturing"), (41, 43, "construction"), (45, 45, "auto"),
    (46, 46, "wholesale"), (47, 47, "retail"), (49, 53, "logistics"), (55, 55, "hospitality"),
    (56, 56, "food_service"), (58, 60, "media"), (61, 61, "it"), (62, 63, "it"), (68, 68, "real_estate"),
    (69, 71, "professional"), (72, 72, "science"), (73, 75, "professional"), (77, 78, "services"),
    (79, 79, "hospitality"), (80, 82, "services"), (85, 85, "education"), (86, 88, "health"),
    (90, 93, "creative"), (95, 96, "services"),
]


def sector_by_okved(code: str | None) -> Sector:
    if not code:
        return SECTORS["other"]
    try:
        head = int(code.split(".")[0][:2])
    except ValueError:
        return SECTORS["other"]
    for lo, hi, key in _RANGES:
        if lo <= head <= hi:
            return SECTORS[key]
    return SECTORS["other"]


REGIONS: dict[str, str] = {
    "16": "Республика Татарстан",
    "18": "Удмуртская Республика",
    "23": "Краснодарский край",
    "50": "Московская область",
    "52": "Нижегородская область",
    "54": "Новосибирская область",
    "61": "Ростовская область",
    "63": "Самарская область",
    "66": "Свердловская область",
    "68": "Тамбовская область",
    "74": "Челябинская область",
    "77": "Москва",
    "78": "Санкт-Петербург",
}


def region_name(code: str | None) -> str:
    return REGIONS.get(code or "", f"Регион {code}" if code else "Регион не указан")
