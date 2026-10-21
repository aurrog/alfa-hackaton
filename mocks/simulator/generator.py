"""Детерминированный генератор профиля для любого корректного ИНН.

Один и тот же ИНН всегда даёт один и тот же профиль: это позволяет подключить
в кабинете произвольную компанию (сценарий S8) и наполнить историю заявок.
Распределения подобраны так, чтобы встречались все исходы: автоодобрение,
контрпредложение, ручная проверка, отказ.
"""

from __future__ import annotations

from datetime import date

from simulator.util import _INN12_1, _INN12_2, _ctrl, months_ago, rng_for

SECTORS = [
    ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания", 0.10),
    ("47.19", "Торговля розничная прочая в неспециализированных магазинах", 0.12),
    ("46.90", "Торговля оптовая неспециализированная", 0.10),
    ("45.20", "Техническое обслуживание и ремонт автотранспортных средств", 0.07),
    ("49.41", "Деятельность автомобильного грузового транспорта", 0.08),
    ("41.20", "Строительство жилых и нежилых зданий", 0.07),
    ("43.31", "Производство штукатурных работ", 0.04),
    ("62.01", "Разработка компьютерного программного обеспечения", 0.08),
    ("25.11", "Производство строительных металлических конструкций", 0.06),
    ("10.71", "Производство хлеба и мучных кондитерских изделий", 0.05),
    ("55.10", "Деятельность гостиниц и прочих мест для временного проживания", 0.04),
    ("86.23", "Стоматологическая практика", 0.05),
    ("96.02", "Предоставление услуг парикмахерскими и салонами красоты", 0.05),
    ("01.13", "Выращивание овощей, бахчевых, корнеплодных и клубнеплодных культур", 0.04),
    ("71.12", "Деятельность в области инженерных изысканий и технического консультирования", 0.05),
]

REGIONS = {"16": "Республика Татарстан, г. Казань", "18": "Удмуртская Республика, г. Ижевск",
           "23": "Краснодарский край, г. Краснодар", "50": "Московская область, г. Химки",
           "52": "Нижегородская область, г. Нижний Новгород", "54": "Новосибирская область, г. Новосибирск",
           "61": "Ростовская область, г. Ростов-на-Дону", "63": "Самарская область, г. Самара",
           "66": "Свердловская область, г. Екатеринбург", "68": "Тамбовская область, г. Тамбов",
           "74": "Челябинская область, г. Челябинск", "77": "г. Москва", "78": "г. Санкт-Петербург"}

STREETS = ["ул. Ленина", "ул. Советская", "ул. Мира", "пр. Победы", "ул. Гагарина", "ул. Садовая", "ул. Заводская",
           "ул. Молодёжная", "ул. Центральная", "ул. Школьная"]
LAST = ["Иванов", "Петров", "Сидоров", "Кузнецов", "Попов", "Васильев", "Соколов", "Михайлов", "Новиков", "Фёдоров",
        "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев"]
FIRST_M = ["Александр", "Сергей", "Андрей", "Дмитрий", "Алексей", "Максим", "Евгений", "Иван", "Михаил", "Артём"]
FIRST_F = ["Анна", "Елена", "Ольга", "Наталья", "Мария", "Татьяна", "Ирина", "Екатерина", "Светлана", "Юлия"]
MID_M = ["Александрович", "Сергеевич", "Андреевич", "Викторович", "Николаевич", "Игоревич", "Олегович"]
MID_F = ["Александровна", "Сергеевна", "Андреевна", "Викторовна", "Николаевна", "Игоревна", "Олеговна"]
BRANDS = ["Альфа", "Вектор", "Гранит", "Меридиан", "Северный ветер", "Престиж", "Ремстрой", "Медведь", "Восход",
          "Квант", "Сфера", "Лидер", "Добрый день", "Импульс", "Форвард", "Сибирь", "Озон-Сервис", "Атлант"]


def _person_name(rng) -> str:
    if rng.random() < 0.6:
        return f"{rng.choice(LAST)} {rng.choice(FIRST_M)} {rng.choice(MID_M)}"
    return f"{rng.choice(LAST)}а {rng.choice(FIRST_F)} {rng.choice(MID_F)}"


def _person_inn(rng, region: str) -> str:
    d = [int(c) for c in region] + [rng.randint(0, 9) for _ in range(8)]
    d.append(_ctrl(d, _INN12_1))
    d.append(_ctrl(d, _INN12_2))
    return "".join(map(str, d))


def generate(inn: str, today: date) -> dict:
    rng = rng_for(inn, "profile")
    is_ip = len(inn) == 12
    region = inn[:2] if inn[:2] in REGIONS else rng.choice(list(REGIONS))
    okved, okved_name, _w = rng.choices(SECTORS, weights=[s[2] for s in SECTORS])[0]
    age = int(rng.choice([rng.randint(4, 14), rng.randint(14, 48), rng.randint(48, 160)]))
    reg = months_ago(age, today)
    scale = rng.choice([0.6, 1.0, 1.0, 1.8, 3.5, 8.0]) if not is_ip else rng.choice([0.4, 0.7, 1.0, 1.4])
    avg = round(rng.lognormvariate(13.7, 0.5) * scale, -3)  # ≈ 0.9 млн ₽/мес × масштаб
    person = _person_name(rng)
    person_inn = inn if is_ip else _person_inn(rng, region)
    brand = rng.choice(BRANDS)
    quality = rng.random()  # 0 — проблемный, 1 — образцовый заёмщик
    overdue = 0 if quality > 0.22 else rng.choice([5, 14, 21, 45, 60, 95, 130])
    owner_overdue = 0 if quality > 0.18 else rng.choice([0, 7, 25, 40, 100])
    inquiries = rng.choice([0, 0, 0, 1, 1, 2]) if quality > 0.22 else rng.choice([2, 4, 6, 9])
    arrears = 0 if quality > 0.1 else round(avg * rng.uniform(0.02, 0.4), -3)
    existing = round(avg * rng.uniform(0, 0.05), -2)
    bank_client = rng.random() < 0.6
    cv = round(rng.uniform(0.05, 0.32), 3)
    house = rng.randint(1, 120)
    name = (f"Индивидуальный предприниматель {person}" if is_ip
            else f"Общество с ограниченной ответственностью «{brand}»")
    short = (f"ИП {person.split()[0]} {person.split()[1][0]}. {person.split()[2][0]}." if is_ip else f"ООО «{brand}»")
    return {
        "scenario": None, "generated": True,
        "type": "IP" if is_ip else "LE", "full_name": name, "short_name": short, "registration_date": reg,
        "kpp": None if is_ip else f"{inn[:4]}01001", "region_code": region,
        "address": f"{REGIONS[region]}, {rng.choice(STREETS)}, д. {house}",
        "mass_address": rng.random() < 0.04,
        "okved": (okved, okved_name), "status": ("active", "Действующий" if is_ip else "Действующее"),
        "employees": rng.randint(1, 8) if is_ip else rng.randint(3, 120),
        "director": {"full_name": person, "inn": person_inn,
                     "position": "Индивидуальный предприниматель" if is_ip else "Генеральный директор", "since": reg},
        "founders": [] if is_ip else [{"name": person, "inn": person_inn, "share": 100.0}],
        "fns": {"revenue": round(avg * 12 * rng.uniform(0.85, 1.1), -3),
                "tax_arrears": {"amount": arrears, "penalties": round(arrears * 0.08, -2)},
                "taxes_paid": round(avg * 12 * 0.06, -3), "tax_regime": rng.choice(["УСН «доходы»", "УСН «доходы минус расходы»", "ОСН"]),
                "disqualified_persons": rng.random() < 0.01, "blocked_accounts": rng.random() < 0.03},
        "msp": {"in_registry": rng.random() < 0.95, "category": "micro" if avg < 10_000_000 else "small"},
        "aml": "hit" if rng.random() < 0.01 else "clear",
        "bki": {"max_overdue_days_24m": overdue, "inquiries_30d": inquiries,
                "active_loans": [] if existing == 0 else [
                    {"creditor": "Другой банк", "type": "working_capital", "amount": round(existing * 30, -3),
                     "balance": round(existing * 18, -3), "monthly_payment": existing}]},
        "persons": [{"full_name": person, "inn": person_inn, "max_overdue_days_24m": owner_overdue,
                     "inquiries_30d": min(inquiries, 3), "active_loans": []}],
        "abs": {"client_since": months_ago(min(age, rng.randint(2, 60)), today), "avg_incoming": avg, "cv": cv,
                "trend": rng.uniform(-0.2, 0.25), "products": []} if bank_client else None,
        "statement": {"avg_incoming": avg, "cv": cv, "trend": rng.uniform(-0.2, 0.25), "bank_bic": "044525225",
                      "account": "40702810" + inn[-10:].rjust(12, "0")[:12]},
    }
