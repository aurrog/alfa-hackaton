"""Черновик кредитного заключения для аналитика.

Собирается детерминированно из досье (все цифры — из данных, без «галлюцинаций»).
Если включена LLM с открытыми весами, она только улучшает связность текста.
Экономия времени аналитика на типовом документе — понятная ценность ИИ.
"""

from __future__ import annotations

from app.domain.decision.engine import _pct
from app.services import llm


def _m(x) -> str:
    return "—" if x is None else f"{float(x):,.0f} ₽".replace(",", " ")


def build_memo(d: dict) -> dict:
    a, c, rec, sc, der = d["application"], d["company"], d.get("recommendation") or {}, d.get("scoring") or {}, d.get("derived") or {}
    lines = [f"# Кредитное заключение (черновик) — заявка {a['number']}", ""]
    lines += ["## 1. Заёмщик",
              f"{c['name']} (ИНН {c['inn']}, ОГРН {c['ogrn']}), зарегистрирован {c['registration_date']}, "
              f"ОКВЭД {c['okved_code']} — {c['okved_name']}. Категория МСП: {c['msp_category'] or 'нет данных'}. "
              f"{'Клиент банка с ' + str(c['bank_client_since']) + '.' if c['is_bank_client'] else 'Не является клиентом банка.'}", ""]
    lines += ["## 2. Запрос",
              f"Продукт «{a['product']['name']}», сумма {_m(a['amount'])}, срок {a['term_months']} мес., цель: {a['purpose']}"
              + (f" ({a['purpose_text']})" if a.get('purpose_text') else "") + ".", ""]
    lines += ["## 3. Финансовое положение",
              f"Подтверждённая выручка: {_m(der.get('monthly_revenue'))} в месяц (источник: {der.get('revenue_source', '—')}); "
              f"заявлено клиентом: {_m(der.get('declared_monthly_revenue'))}. Текущие платежи по кредитам: "
              f"{_m(der.get('existing_monthly_payments'))} в месяц."]
    aff = rec.get("affordability") or {}
    if aff:
        lines.append(f"Операционный денежный поток (оценка по отраслевой маржинальности {aff.get('sector_margin', 0):.0%}): "
                     f"{_m(aff.get('operating_cash_flow'))} в месяц; посильный новый платёж при DSCR ≥ {aff.get('min_dscr')}: "
                     f"{_m(aff.get('max_new_payment'))}. Ограничивающий фактор суммы: {aff.get('binding_cap')}."
                     + (f" DSCR при предлагаемых условиях: {aff.get('dscr_at_offer')}." if aff.get('dscr_at_offer') else ""))
    lines.append("")
    if sc:
        lines += ["## 4. Скоринговая оценка",
                  f"Модель {sc.get('model')}: {sc.get('score')} баллов, PD {_pct(float(sc.get('pd') or 0), 2)}, грейд {sc.get('grade')}."]
        neg = sorted(sc.get("factors") or [], key=lambda f: -f.get("lost_points", 0))[:3]
        neg = [f for f in neg if f.get("lost_points", 0) >= 10]
        if neg:
            lines.append("Факторы, снижающие оценку: " + "; ".join(f"{f['title']} — {f['display_value']}" for f in neg) + ".")
        lines.append("")
    fails = [ch for ch in d.get("checks", []) if ch["result"] in ("fail", "warn", "unavailable")]
    lines.append("## 5. Проверки и риски")
    if fails:
        for ch in fails:
            lines.append(f"- {ch['title']}: {ch['details']} ({ch['source']})")
    else:
        lines.append("- Существенных замечаний по проверкам нет.")
    lines.append("")
    lines.append("## 6. Рекомендация")
    if rec:
        if rec.get("outcome") == "decline":
            lines.append("Рекомендация движка: отказ. Причины: " + "; ".join(r.get("client_text", "") for r in rec.get("reason_codes", [])) + ".")
        else:
            lines.append(f"Рекомендация движка: {'одобрить' if rec.get('outcome') == 'approve' else 'одобрить на изменённых условиях'} "
                         f"{_m(rec.get('amount'))} на {rec.get('term_months')} мес. под {rec.get('rate')}% "
                         f"(платёж {_m(rec.get('monthly_payment'))}).")
            if rec.get("conditions"):
                lines.append("Условия: " + "; ".join(rec["conditions"]) + ".")
        lines.append(f"Уровень полномочий: {rec.get('level_title')}. Версия политики: {rec.get('policy_version')}, модель: {rec.get('model_version')}.")
    if a.get("manual_reasons"):
        lines.append("Основания ручного рассмотрения: " + "; ".join(a["manual_reasons"]) + ".")
    text = "\n".join(lines)
    polished = llm.chat(
        "Ты помогаешь кредитному аналитику. Улучши связность текста кредитного заключения, сохрани структуру, "
        "все цифры и факты без изменений, ничего не добавляй от себя. Ответ — только текст заключения в Markdown.",
        text, max_tokens=900)
    return {"markdown": polished or text, "provider": "llm" if polished else "template"}
