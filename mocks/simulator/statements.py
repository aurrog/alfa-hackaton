"""Синтетическая выписка в формате обмена 1С (1CClientBankExchange, кодировка Windows-1251).

Поступления по месяцам согласованы с профилем компании, есть типичные «шумы»,
которые разборщик должен исключить: перевод между своими счетами и
поступление кредита; есть платежи по кредитам — они учитываются в нагрузке.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from simulator.util import last_months, rng_for, series

PAYERS = [("ООО «Ромашка»", "7701234560"), ("ООО «Северная звезда»", "7802345671"), ("АО «Торговый дом»", "5003456782"),
          ("ООО «Городские сети»", "1604567893"), ("ИП Орлова Т. В.", "540512345678"), ("ООО «Прогресс»", "6605678904"),
          ("ООО «Стандарт»", "6106789015"), ("МБУ «Центр услуг»", "5407890126"), ("ООО «Импульс»", "7708901237"),
          ("ООО «Маркет Плюс»", "7709012348"), ("Эквайринг: возмещение по картам", "7707083893")]
SUPPLIERS = [("ООО «Поставщик»", "7711122233", "Оплата по договору поставки"),
             ("ООО «Аренда-Центр»", "7722233344", "Арендная плата"),
             ("ПАО «Энергосбыт»", "7733344455", "Оплата электроэнергии"),
             ("ООО «Логистика»", "7744455566", "Оплата транспортных услуг")]


def _fmt_amount(x: float) -> str:
    return f"{x:.2f}"


def build_statement(inn: str, profile: dict, today: date | None = None, months: int = 12) -> str:
    today = today or date.today()
    st = profile.get("statement") or {}
    abs_ = profile.get("abs") or {}
    avg = st.get("avg_incoming") or abs_.get("avg_incoming") or 1_000_000
    cv = st.get("cv") or abs_.get("cv") or 0.15
    trend = st.get("trend", abs_.get("trend", 0.0))
    account = st.get("account") or "40702810900000012345"
    rng = rng_for(inn, "statement")
    month_keys = last_months(months, today)
    incoming = series(rng_for(inn, "statement-series"), avg, cv, months, trend)
    loan_payment = sum(lo.get("monthly_payment", 0) for lo in (profile.get("bki") or {}).get("active_loans", []))
    name = profile["short_name"]

    docs: list[dict[str, str]] = []
    num = 100

    def add(day: date, amount: float, incoming_op: bool, cp_name: str, cp_inn: str, purpose: str) -> None:
        nonlocal num
        num += 1
        d = {
            "СекцияДокумент": "Платежное поручение", "Номер": str(num), "Дата": day.strftime("%d.%m.%Y"),
            "Сумма": _fmt_amount(amount),
        }
        if incoming_op:
            d.update({"ПлательщикСчет": "40702810" + cp_inn[-10:].rjust(12, "0")[:12], "Плательщик": cp_name,
                      "ПлательщикИНН": cp_inn, "ПолучательСчет": account, "Получатель": name, "ПолучательИНН": inn,
                      "ДатаПоступило": day.strftime("%d.%m.%Y")})
        else:
            d.update({"ПлательщикСчет": account, "Плательщик": name, "ПлательщикИНН": inn,
                      "ПолучательСчет": "40702810" + cp_inn[-10:].rjust(12, "0")[:12], "Получатель": cp_name,
                      "ПолучательИНН": cp_inn, "ДатаСписано": day.strftime("%d.%m.%Y")})
        d["НазначениеПлатежа"] = purpose
        docs.append(d)

    for mk, total in zip(month_keys, incoming, strict=True):
        y, mth = map(int, mk.split("-"))
        first = date(y, mth, 1)
        n_payers = rng.randint(6, 11)
        weights = [rng.uniform(0.5, 2.0) for _ in range(n_payers)]
        s = sum(weights)
        for i in range(n_payers):
            payer = PAYERS[(i + mth) % len(PAYERS)]
            add(first + timedelta(days=rng.randint(0, 27)), round(total * weights[i] / s, 2), True, payer[0], payer[1],
                f"Оплата по счёту № {rng.randint(10, 999)} за товары и услуги. НДС не облагается")
        spent = total * rng.uniform(0.75, 0.92)
        for sup in SUPPLIERS:
            add(first + timedelta(days=rng.randint(1, 27)), round(spent * rng.uniform(0.12, 0.3), 2), False, sup[0], sup[1],
                f"{sup[2]} за {mth:02d}.{y}")
        add(first + timedelta(days=9), round(spent * 0.18, 2), False, "Сотрудники (реестр)", "", "Перечисление заработной платы по реестру")
        add(first + timedelta(days=24), round(total * 0.04, 2), False, "УФК по г. Москве (ФНС России)", "7727406020",
            "Единый налоговый платёж")
        if loan_payment:
            add(first + timedelta(days=14), round(loan_payment, 2), False, "Банк-кредитор", "7702070139",
                f"Погашение кредита и процентов по кредитному договору № {rng.randint(100, 999)}-К")
    # «шумы», которые должны быть исключены из выручки
    y0, m0 = map(int, month_keys[len(month_keys) // 2].split("-"))
    add(date(y0, m0, 12), round(avg * 0.3, 2), True, name, inn, "Перевод собственных средств между счетами")
    add(date(y0, m0, 15), round(avg * 0.5, 2), True, "АО «Другой банк»", "7702070139",
        "Выдача кредита по кредитному договору № 77-К")

    period_from = date(*map(int, month_keys[0].split("-")), 1)
    last_y, last_m = map(int, month_keys[-1].split("-"))
    period_to = (date(last_y + (last_m == 12), last_m % 12 + 1, 1) - timedelta(days=1))
    docs.sort(key=lambda d: datetime.strptime(d.get("ДатаПоступило") or d.get("ДатаСписано"), "%d.%m.%Y"))
    lines = ["1CClientBankExchange", "ВерсияФормата=1.03", "Кодировка=Windows", "Отправитель=Бухгалтерия предприятия",
             "Получатель=", f"ДатаСоздания={today.strftime('%d.%m.%Y')}", "ВремяСоздания=10:00:00",
             f"ДатаНачала={period_from.strftime('%d.%m.%Y')}", f"ДатаКонца={period_to.strftime('%d.%m.%Y')}",
             f"РасчСчет={account}", "Документ=Платежное поручение",
             "СекцияРасчСчет", f"ДатаНачала={period_from.strftime('%d.%m.%Y')}",
             f"ДатаКонца={period_to.strftime('%d.%m.%Y')}", f"РасчСчет={account}", "КонецРасчСчет"]
    for d in docs:
        lines.append(f"СекцияДокумент={d.pop('СекцияДокумент')}")
        lines += [f"{k}={v}" for k, v in d.items()]
        lines.append("КонецДокумента")
    lines.append("КонецФайла")
    return "\r\n".join(lines) + "\r\n"
