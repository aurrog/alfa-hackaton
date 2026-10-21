"""Профили компаний сквозных сценариев S1–S7 (все данные вымышлены).

Даты задаются относительно текущего дня, поэтому сценарии воспроизводятся
в любой день проверки. Для прочих корректных ИНН профиль генерируется
(см. generator.py).
"""

from __future__ import annotations

from datetime import date

from simulator.util import days_ago, months_ago


def _person(name: str, inn: str, overdue: int = 0, inquiries: int = 0, loans: list | None = None) -> dict:
    return {"full_name": name, "inn": inn, "max_overdue_days_24m": overdue, "inquiries_30d": inquiries,
            "active_loans": loans or []}


def build(today: date) -> dict[str, dict]:
    m = lambda n: months_ago(n, today)  # noqa: E731
    d = lambda n: days_ago(n, today)  # noqa: E731
    return {
        # ------------------------------------------------------------- S1
        "165573184679": {
            "scenario": "S1",
            "type": "IP", "full_name": "Индивидуальный предприниматель Смирнова Анна Сергеевна",
            "short_name": "ИП Смирнова А. С.", "brand": "кофейня «Зёрна»", "registration_date": m(62),
            "region_code": "16", "address": "420111, Республика Татарстан, г. Казань, ул. Баумана, д. 17",
            "okved": ("56.10", "Деятельность ресторанов и услуги по доставке продуктов питания"),
            "status": ("active", "Действующий"), "employees": 9,
            "director": {"full_name": "Смирнова Анна Сергеевна", "inn": "165573184679", "position": "Индивидуальный предприниматель", "since": m(62)},
            "founders": [],
            "fns": {"revenue": 16_200_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 1_150_000,
                    "tax_regime": "УСН «доходы минус расходы»"},
            "msp": {"in_registry": True, "category": "micro"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 0, "active_loans": [
                {"creditor": "Лизинговая компания", "type": "leasing", "amount": 640_000, "balance": 290_000, "monthly_payment": 21_000}]},
            "abs": {"client_since": m(54), "avg_incoming": 1_350_000, "cv": 0.09, "trend": 0.12, "products": []},
        },
        # ------------------------------------------------------------- S2
        "5027841264": {
            "scenario": "S2",
            "type": "LE", "full_name": "Общество с ограниченной ответственностью «ТехноСтрой»",
            "short_name": "ООО «ТехноСтрой»", "registration_date": m(79), "kpp": "503601001",
            "region_code": "50", "address": "142100, Московская область, г. Подольск, ул. Комсомольская, д. 1, стр. 5",
            "okved": ("25.62", "Обработка металлических изделий механическая"),
            "status": ("active", "Действующее"), "employees": 64,
            "director": {"full_name": "Кузнецов Олег Викторович", "inn": "501043321861", "position": "Генеральный директор", "since": d(25)},
            "previous_director": {"full_name": "Лебедев Сергей Петрович", "inn": "501960013362"},
            "founders": [{"name": "Кузнецов Олег Викторович", "inn": "501043321861", "share": 70.0},
                         {"name": "Лебедев Сергей Петрович", "inn": "501960013362", "share": 30.0}],
            "fns": {"revenue": 198_000_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 14_600_000,
                    "tax_regime": "ОСН"},
            "msp": {"in_registry": True, "category": "small"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 4, "active_loans": [
                {"creditor": "Другой банк", "type": "working_capital", "amount": 9_000_000, "balance": 5_100_000, "monthly_payment": 300_000}]},
            "persons": [_person("Кузнецов Олег Викторович", "501043321861", overdue=12, inquiries=1),
                        _person("Лебедев Сергей Петрович", "501960013362")],
            "abs": {"client_since": m(26), "avg_incoming": 17_000_000, "cv": 0.24, "trend": 0.05, "seasonal": 0.2, "products": []},
        },
        # ------------------------------------------------------------- S3
        "667145031828": {
            "scenario": "S3",
            "type": "IP", "full_name": "Индивидуальный предприниматель Морозов Игорь Николаевич",
            "short_name": "ИП Морозов И. Н.", "brand": "автосервис «Мотор»", "registration_date": m(38),
            "region_code": "66", "address": "620102, Свердловская область, г. Екатеринбург, ул. Шаумяна, д. 83",
            "okved": ("45.20", "Техническое обслуживание и ремонт автотранспортных средств"),
            "status": ("active", "Действующий"), "employees": 6,
            "director": {"full_name": "Морозов Игорь Николаевич", "inn": "667145031828", "position": "Индивидуальный предприниматель", "since": m(38)},
            "founders": [],
            "fns": {"revenue": 14_100_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 820_000,
                    "tax_regime": "УСН «доходы»"},
            "msp": {"in_registry": True, "category": "micro"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 0, "active_loans": [
                {"creditor": "Другой банк", "type": "card", "amount": 300_000, "balance": 120_000, "monthly_payment": 15_000}]},
            "abs": {"client_since": m(22), "avg_incoming": 1_200_000, "cv": 0.11, "trend": 0.0, "products": []},
        },
        # ------------------------------------------------------------- S4
        "616421958755": {
            "scenario": "S4",
            "type": "IP", "full_name": "Индивидуальный предприниматель Козлов Иван Петрович",
            "short_name": "ИП Козлов И. П.", "brand": "магазин «Продукты у дома»", "registration_date": m(86),
            "region_code": "61", "address": "344002, Ростовская область, г. Ростов-на-Дону, ул. Пушкинская, д. 42",
            "okved": ("47.11", "Торговля розничная преимущественно пищевыми продуктами в неспециализированных магазинах"),
            "status": ("active", "Действующий"), "employees": 4,
            "director": {"full_name": "Козлов Иван Петрович", "inn": "616421958755", "position": "Индивидуальный предприниматель", "since": m(86)},
            "founders": [],
            "fns": {"revenue": 10_500_000, "tax_arrears": {"amount": 412_000, "penalties": 38_400}, "taxes_paid": 310_000,
                    "tax_regime": "УСН «доходы»"},
            "msp": {"in_registry": True, "category": "micro"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 118, "inquiries_30d": 6, "active_loans": [
                {"creditor": "МФО", "type": "microloan", "amount": 500_000, "balance": 410_000, "monthly_payment": 48_000}]},
            "abs": {"client_since": m(40), "avg_incoming": 900_000, "cv": 0.22, "trend": -0.15, "products": []},
        },
        # ------------------------------------------------------------- S5
        "5406732910": {
            "scenario": "S5",
            "type": "LE", "full_name": "Общество с ограниченной ответственностью «Цифровые решения»",
            "short_name": "ООО «Цифровые решения»", "registration_date": m(55), "kpp": "540601001",
            "region_code": "54", "address": "630099, Новосибирская область, г. Новосибирск, Красный проспект, д. 28, офис 410",
            "okved": ("62.01", "Разработка компьютерного программного обеспечения"),
            "status": ("active", "Действующее"), "employees": 23,
            "director": {"full_name": "Волкова Елена Андреевна", "inn": "548908386352", "position": "Генеральный директор", "since": m(55)},
            "founders": [{"name": "Волкова Елена Андреевна", "inn": "548908386352", "share": 100.0}],
            "fns": {"revenue": 29_600_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 2_300_000,
                    "tax_regime": "УСН «доходы минус расходы»"},
            "msp": {"in_registry": True, "category": "small"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 1, "active_loans": [
                {"creditor": "Другой банк", "type": "overdraft", "amount": 1_000_000, "balance": 400_000, "monthly_payment": 50_000}]},
            "persons": [_person("Волкова Елена Андреевна", "548908386352")],
            "abs": None,  # счёт в другом банке
            "statement": {"avg_incoming": 2_500_000, "cv": 0.13, "trend": 0.1, "bank_bic": "045004641",
                          "account": "40702810844050012345"},
        },
        # ------------------------------------------------------------- S6
        "7816450286": {
            "scenario": "S6",
            "type": "LE", "full_name": "Общество с ограниченной ответственностью «ЛогистикПро»",
            "short_name": "ООО «ЛогистикПро»", "registration_date": m(61), "kpp": "781601001",
            "region_code": "78", "address": "192019, г. Санкт-Петербург, наб. Обводного канала, д. 24, лит. А",
            "okved": ("49.41", "Деятельность автомобильного грузового транспорта"),
            "status": ("active", "Действующее"), "employees": 41,
            "director": {"full_name": "Орлов Дмитрий Сергеевич", "inn": "787940265425", "position": "Генеральный директор", "since": m(61)},
            "founders": [{"name": "Орлов Дмитрий Сергеевич", "inn": "787940265425", "share": 100.0}],
            "fns": {"revenue": 92_000_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 6_900_000,
                    "tax_regime": "ОСН"},
            "msp": {"in_registry": True, "category": "small"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 1, "active_loans": [
                {"creditor": "Лизинговая компания", "type": "leasing", "amount": 12_000_000, "balance": 7_400_000, "monthly_payment": 250_000}]},
            "persons": [_person("Орлов Дмитрий Сергеевич", "787940265425")],
            "abs": {"client_since": m(30), "avg_incoming": 8_000_000, "cv": 0.16, "trend": 0.08, "products": []},
            # БКИ «недоступно» 40 секунд с первого запроса — проверка деградации в ручную проверку
            "faults": [{"source": "bki_company", "mode": "outage", "seconds": 40, "from": "first_call"}],
        },
        # ------------------------------------------------------------- S7
        "7705398129": {
            "scenario": "S7",
            "type": "LE", "full_name": "Общество с ограниченной ответственностью «Вектор»",
            "short_name": "ООО «Вектор»", "registration_date": m(37), "kpp": "770501001",
            "region_code": "77", "address": "115054, г. Москва, ул. Валовая, д. 11/19, помещение 3",
            "okved": ("46.69", "Торговля оптовая прочими машинами и оборудованием"),
            "status": ("liquidating", "Находится в стадии ликвидации"), "status_since": d(9), "employees": 7,
            "director": {"full_name": "Соколов Павел Игоревич", "inn": "772351161526", "position": "Ликвидатор", "since": d(9)},
            "founders": [{"name": "Соколов Павел Игоревич", "inn": "772351161526", "share": 100.0}],
            "fns": {"revenue": 38_000_000, "tax_arrears": {"amount": 0, "penalties": 0}, "taxes_paid": 1_900_000,
                    "tax_regime": "ОСН"},
            "msp": {"in_registry": True, "category": "small"},
            "aml": "clear",
            "bki": {"max_overdue_days_24m": 0, "inquiries_30d": 2, "active_loans": []},
            "persons": [_person("Соколов Павел Игоревич", "772351161526")],
            "abs": {"client_since": m(20), "avg_incoming": 3_100_000, "cv": 0.3, "trend": -0.3, "products": []},
        },
    }


SCENARIO_INNS = ["165573184679", "5027841264", "667145031828", "616421958755", "5406732910", "7816450286", "7705398129"]
