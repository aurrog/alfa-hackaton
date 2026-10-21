"""Реквизиты, калькулятор, отрасли, политика, чек-лист, база знаний."""

from datetime import date

import pytest

from app.domain.calculator import add_months, annuity_payment, effective_annual_rate, loan_summary, max_principal, schedule
from app.domain.checklist import build_checklist, missing_required
from app.domain.decision.policy import DEFAULT_POLICY, EDITABLE, Policy, get_path, set_path
from app.domain.knowledge import search
from app.domain.okved import region_name, sector_by_okved
from app.domain.validators import is_valid_inn, is_valid_ogrn, legal_form_by_inn, make_inn, make_ogrn


# ------------------------------------------------------------------ реквизиты
@pytest.mark.parametrize("inn", ["7707083893", "5027841264", "165573184679", "616421958755", "5406732910"])
def test_valid_inn(inn):
    assert is_valid_inn(inn)


@pytest.mark.parametrize("inn", ["7707083890", "123", "", None, "abcdefghij", "16557318467", "165573184670"])
def test_invalid_inn(inn):
    assert not is_valid_inn(inn)


def test_legal_form_by_inn():
    assert legal_form_by_inn("7707083893") == "LE"
    assert legal_form_by_inn("165573184679") == "IP"


@pytest.mark.parametrize("prefix", ["770708389", "502784126", "1655731846", "6164219587"])
def test_make_inn_roundtrip(prefix):
    inn = make_inn(prefix)
    assert inn.startswith(prefix) and is_valid_inn(inn)


def test_make_inn_rejects_bad_prefix():
    with pytest.raises(ValueError):
        make_inn("12345")


@pytest.mark.parametrize("prefix", ["102770013219", "30416557318467"])
def test_ogrn(prefix):
    ogrn = make_ogrn(prefix)
    assert is_valid_ogrn(ogrn)
    broken = ogrn[:-1] + str((int(ogrn[-1]) + 1) % 10)
    assert not is_valid_ogrn(broken)
    assert not is_valid_ogrn("123") and not is_valid_ogrn(None)


# ------------------------------------------------------------------ калькулятор
def test_annuity_matches_reference():
    # 1,5 млн ₽ на 24 мес. под 21,5% — платёж из сценария S1
    assert annuity_payment(1_500_000, 21.5, 24) == pytest.approx(77_447.36, abs=0.01)


def test_annuity_zero_rate():
    assert annuity_payment(1_200_000, 0, 12) == pytest.approx(100_000)


def test_annuity_requires_positive_term():
    with pytest.raises(ValueError):
        annuity_payment(1000, 10, 0)


def test_max_principal_is_inverse_of_annuity():
    p = annuity_payment(2_000_000, 18.5, 36)
    assert max_principal(p, 18.5, 36) == pytest.approx(2_000_000, rel=1e-9)
    assert max_principal(0, 18.5, 36) == 0


def test_schedule_repays_exactly():
    rows = schedule(1_500_000, 21.5, 24, date(2026, 1, 31))
    assert len(rows) == 24
    assert sum(r.principal for r in rows) == pytest.approx(1_500_000, abs=0.01)
    assert rows[-1].balance == 0
    assert rows[0].date == date(2026, 2, 28)  # конец месяца переносится корректно


def test_add_months_leap_year():
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_loan_summary_and_effective_rate():
    s = loan_summary(1_000_000, 12, 12)
    assert s["overpayment"] == pytest.approx(s["total_payment"] - 1_000_000, abs=0.02)
    assert effective_annual_rate(12) == pytest.approx(12.6825, abs=1e-3)


# ------------------------------------------------------------------ отрасли
@pytest.mark.parametrize("code,key", [("56.10", "food_service"), ("25.62", "manufacturing"), ("62.01", "it"),
                                      ("49.41", "logistics"), ("47.11", "retail"), ("45.20", "auto"), (None, "other"),
                                      ("xx", "other"), ("99.00", "other")])
def test_sector_by_okved(code, key):
    assert sector_by_okved(code).key == key


def test_region_name():
    assert region_name("16") == "Республика Татарстан"
    assert region_name("99").startswith("Регион")
    assert region_name(None) == "Регион не указан"


# ------------------------------------------------------------------ политика
def test_policy_default_and_lookup():
    p = Policy.default()
    assert p.version == 1 and p["key_rate"] == DEFAULT_POLICY["key_rate"]
    assert p["unknown_key"] is None


def test_policy_with_changes_creates_new_config():
    p = Policy.default()
    cfg = p.with_changes({"key_rate": 13.5, "grade_premium.B": 2.0, "authority_limits.analyst": 20_000_000})
    assert cfg["key_rate"] == 13.5 and cfg["grade_premium"]["B"] == 2.0
    assert cfg["authority_limits"]["analyst"] == 20_000_000 and isinstance(cfg["authority_limits"]["analyst"], int)
    assert p["key_rate"] == DEFAULT_POLICY["key_rate"]  # исходная версия не изменилась


@pytest.mark.parametrize("changes", [{"key_rate": 99}, {"hard_stop_overdue_days": 10}, {"min_dscr": 0.2}])
def test_policy_rejects_invalid_changes(changes):
    with pytest.raises(ValueError):
        Policy.default().with_changes(changes)


def test_policy_paths():
    d = {"a": {"b": 1}}
    set_path(d, "a.b", 2)
    assert get_path(d, "a.b") == 2
    assert all(get_path(DEFAULT_POLICY, e["key"]) is not None for e in EDITABLE)


# ------------------------------------------------------------------ чек-лист
def _cl(**kw):
    base = dict(product_code="EXPRESS", product_collateral_from=None, amount=1_000_000, legal_form="IP", purpose="any",
                collateral_type=None, has_internal_turnover=True, uploaded_types=set())
    base.update(kw)
    return build_checklist(**base)


def test_checklist_bank_client_needs_nothing():
    cl = _cl()
    assert not missing_required(cl)
    assert cl[0]["satisfied_by"] == "internal_data"


def test_checklist_other_bank_needs_statement():
    assert [i["doc_type"] for i in missing_required(_cl(has_internal_turnover=False))] == ["bank_statement"]


def test_checklist_large_le_invest():
    cl = _cl(product_code="INVEST", product_collateral_from=10_000_000, amount=40_000_000, legal_form="LE",
             purpose="equipment", collateral_type="real_estate")
    assert {i["doc_type"] for i in missing_required(cl)} == {"financial_statements", "collateral_docs", "purchase_contract"}


def test_checklist_contract_and_uploaded():
    cl = _cl(purpose="contract", uploaded_types={"state_contract"})
    item = next(i for i in cl if i["doc_type"] == "state_contract")
    assert item["required"] and item["satisfied"] and item["satisfied_by"] == "upload"


# ------------------------------------------------------------------ база знаний
@pytest.mark.parametrize("q,expected", [("Что такое DSCR?", "dscr"), ("Почему одобрили меньшую сумму", "counter"),
                                        ("зачем нужна выписка из другого банка", "statement"),
                                        ("как подписать договор без визита", "signing")])
def test_knowledge_search(q, expected):
    assert expected in [h["id"] for h in search(q)]


def test_knowledge_search_nothing():
    assert search("абвгд") == []
