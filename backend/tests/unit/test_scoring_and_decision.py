"""Скоринговая карта и движок кредитного решения (чистые функции без БД)."""

from dataclasses import replace
from datetime import date

import pytest

from app.domain.decision import DecisionContext, Policy, decide
from app.domain.decision.engine import affordability, price, required_level
from app.domain.products import ProductSpec
from app.domain.scoring import FeatureInputs, compute_features, load_scorecard

TODAY = date(2026, 10, 21)
EXPRESS = ProductSpec(code="EXPRESS", name="Экспресс", kind="term_loan", purposes=["any"], min_amount=300_000,
                      max_amount=5_000_000, min_term=3, max_term=36, rate_spread=8.0, turnover_multiple=2.0)
INVEST = ProductSpec(code="INVEST", name="Инвест", kind="term_loan", purposes=["equipment"], min_amount=3_000_000,
                     max_amount=150_000_000, min_term=12, max_term=84, rate_spread=4.5, collateral_required_from=10_000_000,
                     auto_decision=False, min_business_age_months=12)
GOV = ProductSpec(code="GOV", name="Льготный", kind="term_loan", purposes=["equipment"], min_amount=3_000_000,
                  max_amount=30_000_000, min_term=12, max_term=60, rate_mode="key_rate", rate_spread=0, gov_program=True,
                  auto_decision=False)
OVERDRAFT = ProductSpec(code="OVERDRAFT", name="Овердрафт", kind="overdraft", purposes=["cash_gap"], min_amount=100_000,
                        max_amount=10_000_000, min_term=6, max_term=12, rate_spread=6.0, turnover_multiple=0.5)


def features(**kw):
    base = dict(registration_date=date(2020, 1, 1), annual_revenue=16_200_000, turnover_volatility=0.09,
                existing_monthly_payments=21_000, new_loan_payment=79_000, company_max_overdue_days=0,
                owner_max_overdue_days=0, bki_inquiries_30d=0, tax_arrears=0, okved_code="56.10",
                bank_relationship_months=54, today=TODAY)
    base.update(kw)
    return compute_features(FeatureInputs(**base))


def ctx(product=EXPRESS, **kw) -> DecisionContext:
    card = load_scorecard()
    f = kw.pop("features", None) or features()
    base = dict(product=product, amount=1_500_000, term=24, purpose="equipment", legal_form="IP", okved_code="56.10",
                business_age_months=f["business_age_months"], monthly_revenue=1_350_000, revenue_source="обороты в банке",
                declared_monthly_revenue=1_350_000, existing_monthly_payments=21_000, bank_client_months=54)
    base.update(kw)
    c = DecisionContext(**base)
    c.score = card.score(f)
    return c


P = Policy.default()


# ------------------------------------------------------------------ скоринг
def test_scorecard_loads_and_has_ten_factors():
    card = load_scorecard()
    assert card.model_id and card.version
    assert len(card.spec["features"]) == 10
    assert [g["grade"] for g in card.grades] == ["A", "B", "C", "D", "E"]


def test_good_profile_is_grade_a():
    s = load_scorecard().score(features())
    assert s.grade == "A" and s.pd < 0.02 and not s.incomplete
    assert len(s.factors) == 10


def test_bad_profile_is_grade_e():
    s = load_scorecard().score(features(company_max_overdue_days=120, owner_max_overdue_days=120, bki_inquiries_30d=9,
                                        tax_arrears=500_000, turnover_volatility=0.7, registration_date=date(2026, 6, 1),
                                        annual_revenue=3_000_000, existing_monthly_payments=150_000))
    assert s.grade == "E" and s.pd > 0.15
    assert s.negatives(3)[0].lost_points >= 50


def test_pd_decreases_with_score():
    card = load_scorecard()
    pds = [card.pd_from_score(x) for x in range(450, 750, 25)]
    assert all(a > b for a, b in zip(pds, pds[1:], strict=False))


def test_missing_data_is_conservative():
    full = load_scorecard().score(features())
    partial = load_scorecard().score(features(company_max_overdue_days=None, annual_revenue=None))
    assert partial.score < full.score and partial.incomplete


def test_features_debt_load_and_age():
    f = features()
    assert f["business_age_months"] == 81
    assert f["debt_load"] == pytest.approx((21_000 + 79_000) / 1_350_000, rel=1e-3)
    assert f["industry_risk"] == "high"


def test_explanation_lists_positives_and_negatives():
    s = load_scorecard().score(features(bki_inquiries_30d=5))
    assert s.positives(3) and all(p.lost_points <= 5 for p in s.positives(3))
    assert any(n.name == "bki_inquiries_30d" for n in s.negatives(3))


# ------------------------------------------------------------------ цена и посильность
def test_price_by_grade_and_discounts():
    c = ctx()
    assert price(c, P, "A", secured=False) == 21.5  # 14 + 8 − 0,5 (клиент банка ≥ 12 мес.)
    assert price(replace(c, bank_client_months=0), P, "B", secured=True) == 14 + 8 + 1.5 - 1.0
    assert price(ctx(product=GOV), P, "C", secured=False) == 14.0  # льготная программа — ключевая ставка


def test_affordability_dscr_math():
    a = affordability(ctx(), P, rate=21.5, term=24, secured=False)
    ocf = 1_350_000 * 0.12
    assert a["operating_cash_flow"] == pytest.approx(ocf)
    assert a["max_new_payment"] == pytest.approx(ocf / 1.3 - 21_000, rel=1e-6)
    assert a["binding_cap"] in a["caps"] and a["approved_max"] % 50_000 == 0


def test_overdraft_affordability_uses_interest_plus_principal_share():
    a = affordability(ctx(product=OVERDRAFT, amount=500_000, term=12), P, rate=20, term=12, secured=False)
    assert a["caps"]["turnover"] == pytest.approx(0.5 * 1_350_000)


# ------------------------------------------------------------------ решение
def test_auto_approve_good_client():
    r = decide(ctx(), P)
    assert (r.outcome, r.route, r.required_level) == ("approve", "auto_offer", "auto")
    assert r.amount == 1_500_000 and r.term == 24 and r.rate == 21.5
    assert r.monthly_payment == pytest.approx(77_447.36, abs=0.01)
    assert r.affordability["dscr_at_offer"] >= 1.3


def test_counter_offer_by_term_extension():
    r = decide(ctx(amount=2_000_000, term=12), P)
    assert r.outcome == "counter_offer" and r.amount == 2_000_000 and r.term > 12
    assert any("Срок увеличен" in c for c in r.counter_changes)


def test_counter_offer_by_amount_reduction():
    r = decide(ctx(amount=3_000_000, term=12, monthly_revenue=1_200_000, okved_code="45.20"), P)
    assert r.outcome == "counter_offer" and r.amount < 3_000_000
    assert r.counter_changes[0].startswith("Сумма уменьшена")


def test_decline_when_nothing_affordable():
    r = decide(ctx(amount=5_000_000, monthly_revenue=150_000, existing_monthly_payments=10_000), P)
    assert r.outcome == "decline"
    assert "LOW_AFFORDABILITY" in [x["code"] for x in r.reason_codes]


@pytest.mark.parametrize("kw,code", [
    ({"company_status": "liquidating"}, "STOP_COMPANY_STATUS"),
    ({"aml_hit": True}, "STOP_AML"),
    ({"company_max_overdue_days": 118}, "OVERDUE_COMPANY"),
    ({"tax_arrears": 450_000, "monthly_revenue": 900_000}, "TAX_ARREARS"),
    ({"disqualified_director": True}, "STOP_DISQUALIFIED"),
])
def test_stop_factors_decline_automatically(kw, code):
    r = decide(ctx(**kw), P)
    assert r.outcome == "decline" and r.route == "auto_decline"
    assert code in [x["code"] for x in r.reason_codes]
    assert all(x["client_text"] and x["hint"] is not None for x in r.reason_codes)


def test_small_tax_arrears_is_not_a_stop():
    r = decide(ctx(tax_arrears=20_000), P)
    assert r.outcome == "approve"
    assert next(c for c in r.checks if c.code == "TAX_ARREARS").effect is None


def test_source_unavailable_refers_to_manual_not_decline():
    r = decide(ctx(unavailable_sources=["bki_company"], company_max_overdue_days=None), P)
    assert r.route == "refer"
    assert any("БКИ" in m for m in r.manual_reasons)


def test_registry_mismatch_refers_to_manual():
    r = decide(ctx(registry_mismatches=["Руководитель в анкете не совпадает с ЕГРЮЛ"]), P)
    assert r.route == "refer" and r.outcome == "approve"


def test_revenue_deviation_and_unverified_revenue():
    r = decide(ctx(declared_monthly_revenue=3_000_000), P)
    assert r.route == "refer" and any("выручки" in m for m in r.manual_reasons)
    r2 = decide(ctx(revenue_source="анкета"), P)
    assert r2.route == "refer"


def test_amount_above_auto_limit_requires_specialist_and_committee():
    c = ctx(product=INVEST, amount=40_000_000, term=60, purpose="equipment", legal_form="LE", okved_code="25.62",
            monthly_revenue=17_000_000, declared_monthly_revenue=17_000_000, existing_monthly_payments=300_000,
            collateral_type="real_estate", collateral_value=60_000_000, bank_client_months=26,
            features=features(okved_code="25.62", annual_revenue=198_000_000, turnover_volatility=0.24, bki_inquiries_30d=4,
                              owner_max_overdue_days=12, existing_monthly_payments=300_000, new_loan_payment=1_060_000,
                              bank_relationship_months=26))
    r = decide(c, P)
    assert c.score.grade == "B"
    assert r.outcome == "approve" and r.route == "refer" and r.required_level == "committee"
    assert r.rate == 18.5  # 14 + 4,5 + 1,5 (B) − 0,5 (клиент) − 1 (залог)
    assert any("Поручительство" in x for x in r.conditions)


def test_required_levels():
    assert required_level(P, 5_000_000, "B") == "analyst"
    assert required_level(P, 20_000_000, "B") == "senior_analyst"
    assert required_level(P, 40_000_000, "A") == "committee"
    assert required_level(P, 1_000_000, "D") == "committee"


def test_gov_program_requires_priority_sector():
    r = decide(ctx(product=GOV, amount=5_000_000, term=36), P)  # общепит — не приоритетная отрасль
    assert r.outcome == "decline" and "GOV_ELIGIBILITY" in [x["code"] for x in r.reason_codes]


def test_sticky_manual_keeps_manual_route():
    r = decide(ctx(sticky_manual=True), P)
    assert r.route == "refer" and r.required_level == "analyst"


def test_policy_change_affects_rate():
    cheaper = Policy(2, Policy.default().with_changes({"key_rate": 12.0}))
    assert decide(ctx(), cheaper).rate == 19.5
