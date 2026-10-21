"""Доступность и подбор продуктов, персональная лента, разбор банковской выписки."""

from datetime import date

import pytest

from app.domain.feed import FeedProfile, Interactions, learn, rank
from app.domain.products import CompanyProfile, Need, ProductSpec, eligibility, recommend
from app.domain.statement_parser import StatementError, analyze

TODAY = date(2026, 10, 21)
EXPRESS = ProductSpec(code="EXPRESS", name="Экспресс", kind="term_loan", purposes=["working_capital", "equipment", "any"],
                      min_amount=300_000, max_amount=5_000_000, min_term=3, max_term=36, rate_spread=8.0,
                      turnover_multiple=2.0, decision_time="за минуты")
OVERDRAFT = ProductSpec(code="OVERDRAFT", name="Овердрафт", kind="overdraft", purposes=["cash_gap", "working_capital"],
                        min_amount=100_000, max_amount=10_000_000, min_term=6, max_term=12, rate_spread=6.0,
                        requires_bank_client=True, min_bank_client_months=3, turnover_multiple=0.5)
GOV = ProductSpec(code="GOV", name="Льготный", kind="term_loan", purposes=["equipment"], min_amount=3_000_000,
                  max_amount=30_000_000, min_term=12, max_term=60, rate_mode="key_rate", gov_program=True,
                  min_business_age_months=12, auto_decision=False)
LE_ONLY = ProductSpec(code="LE", name="Только ЮЛ", kind="term_loan", purposes=["any"], min_amount=1, max_amount=10,
                      min_term=1, max_term=2, legal_forms=["LE"])


def company(**kw):
    base = dict(inn="165573184679", legal_form="IP", okved_code="56.10", region_code="16",
                registration_date=date(2020, 1, 1), msp_category="micro", is_bank_client=True, bank_client_months=54,
                avg_monthly_turnover=1_350_000)
    base.update(kw)
    return CompanyProfile(**base)


# ------------------------------------------------------------------ продукты
def test_eligible_product():
    assert eligibility(EXPRESS, company(), 1_000_000, 24, TODAY) == []


def test_eligibility_reasons():
    assert eligibility(LE_ONLY, company(), today=TODAY)[0].startswith("Продукт доступен только")
    assert any("срок работы" in r for r in eligibility(EXPRESS, company(registration_date=date(2026, 8, 1)), today=TODAY))
    assert any("расчётный счёт" in r for r in eligibility(OVERDRAFT, company(is_bank_client=False, bank_client_months=0), today=TODAY))
    assert any("приоритетные" in r for r in eligibility(GOV, company(), today=TODAY))
    assert eligibility(GOV, company(okved_code="25.62"), today=TODAY) == []
    assert any("Сумма" in r for r in eligibility(EXPRESS, company(), 10_000_000, 12, TODAY))
    assert any("действующая" in r for r in eligibility(EXPRESS, company(status="liquidating"), today=TODAY))


def test_recommend_prefers_purpose_and_preapproved():
    recs = recommend([EXPRESS, OVERDRAFT, GOV], Need(purpose="equipment", amount=1_500_000, term_months=24, urgent=True),
                     company(), 14.0, {"EXPRESS": 2_000_000}, TODAY)
    assert recs[0]["code"] == "EXPRESS" and recs[0]["best"]
    assert any("Предварительно одобрено" in p for p in recs[0]["pros"])
    assert recs[0]["monthly_payment_from"] > 0
    gov = next(r for r in recs if r["code"] == "GOV")
    assert not gov["eligible"] and gov["blockers"]


def test_recommend_regular_need_prefers_overdraft():
    recs = recommend([EXPRESS, OVERDRAFT], Need(purpose="cash_gap", amount=500_000, term_months=12, regular=True),
                     company(), 14.0, today=TODAY)
    assert recs[0]["code"] == "OVERDRAFT" and recs[0]["payment_kind"] == "interest_only"


def test_recommend_adjusts_term_and_minimum():
    recs = recommend([GOV], Need(purpose="equipment", amount=1_000_000, term_months=6), company(okved_code="25.62"), 14.0, today=TODAY)
    r = recs[0]
    assert r["term_months"] == 12 and r["amount"] == 3_000_000
    assert any("Срок скорректирован" in w for w in r["warnings"])


# ------------------------------------------------------------------ лента
def profile(**kw):
    base = dict(sector_key="food_service", sector_name="Общественное питание", region_code="16",
                region_name="Республика Татарстан", legal_form="IP", msp_category="micro", bank_client=True,
                gov_priority=False, stages={"none"}, decline_reasons=set(), products=set())
    base.update(kw)
    return FeedProfile(**base)


ITEMS = [
    {"id": "all", "title": "Всем", "category": "market", "priority": 2, "published_at": "2026-10-20", "audience": {}, "topics": ["credit"]},
    {"id": "horeca", "title": "Общепит", "category": "industry", "priority": 1, "published_at": "2026-10-15",
     "audience": {"sectors": ["food_service"]}, "strict": ["sectors"], "topics": ["horeca"]},
    {"id": "it", "title": "IT", "category": "industry", "priority": 3, "published_at": "2026-10-20",
     "audience": {"sectors": ["it"]}, "strict": ["sectors"], "topics": ["it"]},
    {"id": "tax", "title": "Долг по налогам", "category": "taxes", "priority": 1, "published_at": "2026-10-01",
     "audience": {"decline_reasons": ["TAX_ARREARS"]}, "strict": ["decline_reasons"], "topics": ["taxes"]},
    {"id": "old", "title": "Старое", "category": "education", "priority": 0, "published_at": "2025-01-01", "audience": {}, "topics": ["cashflow"]},
]


def test_feed_strict_audience_excludes_irrelevant():
    ids = [x["id"] for x in rank(ITEMS, profile(), Interactions(), TODAY)]
    assert "horeca" in ids and "it" not in ids and "tax" not in ids


def test_feed_decline_reason_surfaces_help():
    ranked = rank(ITEMS, profile(stages={"declined"}, decline_reasons={"TAX_ARREARS"}), Interactions(), TODAY)
    tax = next(x for x in ranked if x["id"] == "tax")
    assert tax["why"] and "отказа" in tax["why"][0]


def test_feed_hidden_and_learning():
    inter = Interactions(hidden={"horeca"})
    assert "horeca" not in [x["id"] for x in rank(ITEMS, profile(), inter, TODAY)]
    w = learn({}, ["cashflow"], "like")
    w = learn(w, ["cashflow"], "open")
    assert w["cashflow"] == 1.5
    boosted = rank(ITEMS, profile(), Interactions(topic_weights=w), TODAY)
    plain = rank(ITEMS, profile(), Interactions(), TODAY)
    rel = lambda lst: next(x["relevance"] for x in lst if x["id"] == "old")  # noqa: E731
    assert rel(boosted) > rel(plain)
    assert learn({"x": 4.9}, ["x"], "like")["x"] == 5.0  # ограничение сверху


def test_feed_every_card_explains_itself():
    assert all(x["why"] for x in rank(ITEMS, profile(), Interactions(selected_topics={"credit"}), TODAY))


# ------------------------------------------------------------------ выписка
INN = "5406732910"


def one_c(ops: list[tuple[str, float, bool, str, str]]) -> bytes:
    lines = ["1CClientBankExchange", "ВерсияФормата=1.03", "Кодировка=Windows", "РасчСчет=40702810000000000001"]
    for i, (day, amount, incoming, cp_inn, purpose) in enumerate(ops):
        lines += ["СекцияДокумент=Платежное поручение", f"Номер={i}", f"Дата={day}", f"Сумма={amount:.2f}"]
        if incoming:
            lines += [f"ПлательщикИНН={cp_inn}", "Плательщик=Покупатель", f"ПолучательИНН={INN}",
                      "ПолучательСчет=40702810000000000001", f"ДатаПоступило={day}"]
        else:
            lines += [f"ПлательщикИНН={INN}", "ПлательщикСчет=40702810000000000001", f"ПолучательИНН={cp_inn}",
                      "Получатель=Поставщик", f"ДатаСписано={day}"]
        lines += [f"НазначениеПлатежа={purpose}", "КонецДокумента"]
    lines.append("КонецФайла")
    return "\r\n".join(lines).encode("cp1251")


def test_statement_1c_cp1251_and_exclusions():
    ops = []
    for m in range(1, 7):
        ops.append((f"10.{m:02d}.2026", 1_000_000, True, "7701234560", "Оплата по счёту"))
        ops.append((f"15.{m:02d}.2026", 50_000, False, "7702070139", "Погашение кредита по договору 1"))
    ops.append(("12.03.2026", 300_000, True, INN, "Перевод собственных средств"))
    ops.append(("13.03.2026", 500_000, True, "7702070139", "Выдача кредита по договору 77"))
    st = analyze(one_c(ops), INN)
    assert st["format"] == "1c" and st["months_covered"] == 6
    assert st["avg_monthly_incoming"] == pytest.approx(1_000_000)
    assert st["own_transfers_excluded"] == 300_000 and st["loan_proceeds_excluded"] == 500_000
    assert st["debt_payments_monthly"] == pytest.approx(50_000)
    assert st["turnover_volatility"] == pytest.approx(0)
    assert any("одного покупателя" in w for w in st["warnings"])


def test_statement_csv_short_period_warning():
    csv = "date;amount;direction;counterparty_inn;purpose\n2026-09-01;100000;in;7701234560;Оплата\n2026-10-01;150000;in;7801234561;Оплата\n"
    st = analyze(csv.encode(), INN)
    assert st["format"] == "csv" and st["months_covered"] == 2
    assert any("не менее 6" in w for w in st["warnings"])


@pytest.mark.parametrize("raw", [b"just text", b"date;amount\n1;2\n", "1CClientBankExchange\r\nКонецФайла".encode("cp1251"),
                                 b"date;amount;direction\n2026-01-01;100;sideways\n"])
def test_statement_errors(raw):
    with pytest.raises(StatementError):
        analyze(raw, INN)
