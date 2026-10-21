"""Динамический чек-лист документов: только то, что действительно нужно
для выбранного продукта, суммы, формы бизнеса и данных, которые уже есть в банке."""

from __future__ import annotations

DOC_TYPES: dict[str, dict[str, str]] = {
    "bank_statement": {
        "title": "Выписка по расчётному счёту за 12 месяцев",
        "hint": "Файл выгрузки из банк-клиента в формате 1С (kl_to_1c.txt) или CSV — обороты рассчитаются автоматически.",
    },
    "financial_statements": {
        "title": "Бухгалтерская отчётность за последний год",
        "hint": "Бухгалтерский баланс и отчёт о финансовых результатах (PDF или скан).",
    },
    "collateral_docs": {
        "title": "Документы по залогу",
        "hint": "ПТС/ПСМ, договор купли-продажи оборудования или выписка ЕГРН — в зависимости от предмета залога.",
    },
    "purchase_contract": {
        "title": "Договор или счёт на приобретение",
        "hint": "Подтверждает целевое использование: что покупается, у кого и за сколько.",
    },
    "state_contract": {
        "title": "Контракт с заказчиком",
        "hint": "Контракт по 44-ФЗ/223-ФЗ или договор с крупным заказчиком.",
    },
    "explanation": {
        "title": "Пояснение",
        "hint": "Письмо или документ с пояснениями по запросу банка.",
    },
    "other": {"title": "Прочие документы", "hint": "Любые документы, которые помогут рассмотреть заявку."},
}


def build_checklist(*, product_code: str, product_collateral_from: float | None, amount: float,
                    legal_form: str, purpose: str, collateral_type: str | None,
                    has_internal_turnover: bool, uploaded_types: set[str]) -> list[dict]:
    items: list[dict] = []

    def add(doc_type: str, required: bool, reason: str, satisfied_by: str | None = None) -> None:
        meta = DOC_TYPES[doc_type]
        satisfied = satisfied_by is not None or doc_type in uploaded_types
        items.append({
            "doc_type": doc_type,
            "title": meta["title"],
            "hint": meta["hint"],
            "required": required,
            "reason": reason,
            "satisfied": satisfied,
            "satisfied_by": satisfied_by or ("upload" if doc_type in uploaded_types else None),
        })

    if has_internal_turnover:
        add("bank_statement", False, "Не нужна: банк видит обороты по вашему расчётному счёту", "internal_data")
    else:
        add("bank_statement", True, "Нужна, чтобы оценить обороты: расчётный счёт открыт в другом банке")

    if legal_form == "LE" and amount > 10_000_000:
        add("financial_statements", True, "Для юридических лиц при сумме свыше 10 млн ₽")

    needs_collateral = product_collateral_from is not None and amount >= product_collateral_from
    if (collateral_type and collateral_type != "none") or needs_collateral:
        add("collateral_docs", True,
            "Вы указали залог" if collateral_type and collateral_type != "none"
            else "По продукту при такой сумме требуется залог")

    if product_code == "INVEST" and purpose in ("equipment", "expansion"):
        add("purchase_contract", True, "Подтверждение целевого использования средств")

    if purpose == "contract":
        add("state_contract", True, "Финансирование под исполнение контракта")

    return items


def missing_required(checklist: list[dict]) -> list[dict]:
    return [i for i in checklist if i["required"] and not i["satisfied"]]
