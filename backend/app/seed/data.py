"""Синтетические справочники и тестовые учётные записи. Все люди и компании вымышлены."""

from __future__ import annotations

DEMO_PASSWORD = "Demo-2026"

# Карточки компаний «устарели» относительно свежей выписки ЕГРЮЛ — так проверяется сверка
# при обогащении: S2 — сменился руководитель, S7 — компания вошла в стадию ликвидации.
STALE_CARD: dict[str, dict] = {
    "5027841264": {"director_name": "Лебедев Сергей Петрович", "checked_days_ago": 120,
                   "snapshot_director": {"full_name": "Лебедев Сергей Петрович", "inn": "501960013362",
                                         "position": "Генеральный директор"}},
    "7705398129": {"status": "active", "checked_days_ago": 60,
                   "snapshot_director": {"full_name": "Соколов Павел Игоревич", "inn": "772351161526",
                                         "position": "Генеральный директор"},
                   "snapshot_status": {"code": "active", "name": "Действующее"}},
}

CLIENTS: list[dict] = [
    {"email": "anna@kofe.test", "full_name": "Смирнова Анна Сергеевна", "phone": "+7 917 555-01-01",
     "personal_inn": "165573184679", "birth_date": "1988-04-12",
     "companies": [{"inn": "165573184679", "role": "owner", "can_sign": True, "beneficiary": True,
                    "position": "Индивидуальный предприниматель"}],
     "note": "S1 · ИП, кофейня, клиент банка: предодобренный кредит → автоодобрение → подпись → выдача"},
    {"email": "irina@technostroy.test", "full_name": "Белова Ирина Викторовна", "phone": "+7 926 555-02-02",
     "companies": [{"inn": "5027841264", "role": "accountant", "can_sign": False, "beneficiary": False,
                    "position": "Главный бухгалтер"}],
     "note": "S2 · бухгалтер ООО «ТехноСтрой» без права подписи: готовит заявку на 40 млн ₽ и передаёт директору"},
    {"email": "oleg@technostroy.test", "full_name": "Кузнецов Олег Викторович", "phone": "+7 926 555-02-03",
     "personal_inn": "501043321861", "birth_date": "1979-09-03",
     "companies": [{"inn": "5027841264", "role": "director", "can_sign": True, "beneficiary": True,
                    "position": "Генеральный директор"}],
     "note": "S2 · генеральный директор: подписывает → аналитик → кредитный комитет → выдача"},
    {"email": "igor@motor.test", "full_name": "Морозов Игорь Николаевич", "phone": "+7 912 555-03-03",
     "personal_inn": "667145031828", "birth_date": "1985-01-20",
     "companies": [{"inn": "667145031828", "role": "owner", "can_sign": True, "beneficiary": True,
                    "position": "Индивидуальный предприниматель"}],
     "note": "S3 · ИП, автосервис: просит больше посильного → контрпредложение"},
    {"email": "ivan@kozlov-shop.test", "full_name": "Козлов Иван Петрович", "phone": "+7 918 555-04-04",
     "personal_inn": "616421958755", "birth_date": "1976-07-30",
     "companies": [{"inn": "616421958755", "role": "owner", "can_sign": True, "beneficiary": True,
                    "position": "Индивидуальный предприниматель"}],
     "note": "S4 · ИП, магазин: просрочка 90+ и налоговый долг → отказ с причинами, лента подстраивается"},
    {"email": "elena@cifra.test", "full_name": "Волкова Елена Андреевна", "phone": "+7 913 555-05-05",
     "personal_inn": "548908386352", "birth_date": "1990-11-02",
     "companies": [{"inn": "5406732910", "role": "director", "can_sign": True, "beneficiary": True,
                    "position": "Генеральный директор"}],
     "note": "S5 · ООО «Цифровые решения», счёт в другом банке: запрос выписки → разбор 1С → одобрение"},
    {"email": "dmitry@logistikpro.test", "full_name": "Орлов Дмитрий Сергеевич", "phone": "+7 921 555-06-06",
     "personal_inn": "787940265425", "birth_date": "1982-03-15",
     "companies": [{"inn": "7816450286", "role": "director", "can_sign": True, "beneficiary": True,
                    "position": "Генеральный директор"}],
     "note": "S6 · ООО «ЛогистикПро»: сбой БКИ → ручная проверка → перезапрос → одобрение"},
    {"email": "pavel@vector.test", "full_name": "Соколов Павел Игоревич", "phone": "+7 903 555-07-07",
     "personal_inn": "772351161526", "birth_date": "1987-06-09",
     "companies": [{"inn": "7705398129", "role": "director", "can_sign": True, "beneficiary": True,
                    "position": "Генеральный директор"}],
     "note": "S7 · ООО «Вектор»: ликвидация по свежему ЕГРЮЛ → стоп-фактор"},
    {"email": "new@client.test", "full_name": "Новиков Артём Олегович", "phone": "+7 999 555-08-08",
     "companies": [],
     "note": "S8 · новый пользователь без компаний: подключите любую компанию по ИНН"},
]

BANK_USERS: list[dict] = [
    {"email": "analyst@bank.test", "full_name": "Ковалёва Марина Андреевна", "role": "analyst",
     "position": "Кредитный аналитик", "limit": 15_000_000,
     "note": "Кредитный аналитик: очередь, досье, решения до 15 млн ₽, эскалация на комитет"},
    {"email": "senior@bank.test", "full_name": "Григорьев Алексей Павлович", "role": "senior_analyst",
     "position": "Старший кредитный аналитик", "limit": 30_000_000,
     "note": "Старший аналитик: решения до 30 млн ₽"},
    {"email": "risk@bank.test", "full_name": "Тихонова Светлана Игоревна", "role": "risk_manager",
     "position": "Риск-менеджер, секретарь кредитного комитета", "limit": None,
     "note": "Риск-менеджер: решения кредитного комитета, кредитная политика"},
    {"email": "admin@bank.test", "full_name": "Захаров Никита Сергеевич", "role": "admin",
     "position": "Владелец продукта «Кредитный кабинет МСБ»", "limit": None,
     "note": "Владелец продукта: дашборд процесса, кредитная политика, журнал аудита, мониторинг"},
]

PRODUCTS: list[dict] = [
    {"code": "EXPRESS", "name": "Экспресс-кредит", "kind": "term_loan", "sort_order": 10,
     "tagline": "До 5 млн ₽ без залога с решением за несколько минут",
     "description": "Кредит на любые цели бизнеса без залога. Клиентам банка — предодобренный лимит по оборотам "
                    "и решение без документов, остальным — по выписке из другого банка.",
     "purposes": ["working_capital", "equipment", "expansion", "any"], "min_amount": 300_000, "max_amount": 5_000_000,
     "min_term": 3, "max_term": 36, "rate_spread": 8.0, "min_business_age_months": 6, "turnover_multiple": 2.0,
     "auto_decision": True, "decision_time": "Решение за несколько минут",
     "features": ["Без залога", "Только поручительство собственника для ООО", "Досрочное погашение без комиссий"]},
    {"code": "WORKING_CAPITAL", "name": "Кредит на пополнение оборотных средств", "kind": "term_loan", "sort_order": 20,
     "tagline": "До 50 млн ₽ на закупки, запасы и исполнение контрактов",
     "description": "Срочный кредит под оборотные нужды: закупка товара и сырья, сезонные запасы, исполнение контрактов. "
                    "До 15 млн ₽ — без залога.",
     "purposes": ["working_capital", "contract", "any"], "min_amount": 1_000_000, "max_amount": 50_000_000,
     "min_term": 6, "max_term": 36, "rate_spread": 5.0, "min_business_age_months": 12,
     "collateral_required_from": 15_000_000, "auto_decision": True, "decision_time": "Решение за 1 рабочий день",
     "features": ["До 15 млн ₽ без залога", "Отсрочка погашения основного долга до 3 мес.", "Ставка ниже экспресс-кредита"]},
    {"code": "INVEST", "name": "Инвестиционный кредит", "kind": "term_loan", "sort_order": 30,
     "tagline": "Оборудование, транспорт, ремонт и развитие — до 150 млн ₽ на срок до 7 лет",
     "description": "Долгосрочный кредит на покупку оборудования и транспорта, ремонт и открытие новых точек. "
                    "Залогом может выступать приобретаемое имущество.",
     "purposes": ["equipment", "expansion"], "min_amount": 3_000_000, "max_amount": 150_000_000,
     "min_term": 12, "max_term": 84, "rate_spread": 4.5, "min_business_age_months": 12,
     "collateral_required_from": 10_000_000, "auto_decision": False, "decision_time": "Решение за 1–2 рабочих дня",
     "features": ["Срок до 7 лет", "Залог — приобретаемое имущество", "Скидка к ставке за залог"]},
    {"code": "OVERDRAFT", "name": "Овердрафт", "kind": "overdraft", "sort_order": 40,
     "tagline": "Лимит на расчётном счёте для кассовых разрывов",
     "description": "Деньги поступают автоматически, когда на счёте не хватает средств для платежа. Проценты — только "
                    "за дни фактического использования. Лимит — до 50% среднемесячных поступлений.",
     "purposes": ["cash_gap", "working_capital"], "min_amount": 100_000, "max_amount": 10_000_000,
     "min_term": 6, "max_term": 12, "rate_spread": 6.0, "min_business_age_months": 6, "requires_bank_client": True,
     "min_bank_client_months": 3, "turnover_multiple": 0.5, "auto_decision": True,
     "decision_time": "Решение за несколько минут",
     "features": ["Проценты только за использованные дни", "Работает автоматически", "Лимит растёт вместе с оборотами"]},
    {"code": "CREDIT_LINE", "name": "Возобновляемая кредитная линия", "kind": "credit_line", "sort_order": 50,
     "tagline": "Лимит до 100 млн ₽: берите траншами, возвращайте и берите снова",
     "description": "Для регулярной закупки и исполнения контрактов: транши по заявке в кабинете, проценты на "
                    "фактическую задолженность.",
     "purposes": ["working_capital", "contract", "cash_gap"], "min_amount": 3_000_000, "max_amount": 100_000_000,
     "min_term": 12, "max_term": 36, "rate_spread": 5.0, "min_business_age_months": 12,
     "collateral_required_from": 20_000_000, "auto_decision": False, "decision_time": "Решение за 2–3 рабочих дня",
     "features": ["Транши по заявке в кабинете", "Проценты на фактическую задолженность", "Лимит на 3 года"]},
    {"code": "GOV_KEY_RATE", "name": "Льготный кредит по ключевой ставке", "kind": "term_loan", "sort_order": 60,
     "rate_mode": "key_rate", "tagline": "Ставка равна ключевой ставке Банка России — для приоритетных отраслей",
     "description": "Программа кредитования МСП приоритетных отраслей (обрабатывающие производства, логистика, туризм, IT, "
                    "наука, креативные индустрии) по ставке, равной ключевой. Нужна запись в реестре МСП; лимит "
                    "программы — до 30 млн ₽ на заёмщика.",
     "purposes": ["equipment", "expansion", "working_capital"], "min_amount": 3_000_000, "max_amount": 30_000_000,
     "min_term": 12, "max_term": 60, "rate_spread": 0.0, "min_business_age_months": 12, "gov_program": True,
     "collateral_required_from": 30_000_000, "auto_decision": False, "decision_time": "Решение за 2–3 рабочих дня",
     "features": ["Ставка = ключевая ставка ЦБ", "Поручительство Корпорации МСП", "Только приоритетные отрасли"]},
]
