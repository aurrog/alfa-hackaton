"""Разбор банковской выписки (формат обмена 1С «1CClientBankExchange» или CSV)
и расчёт показателей, которые нужны кредитному конвейеру:
среднемесячные «чистые» поступления, их стабильность, платежи по кредитам,
концентрация на покупателях.

Это прикладная «распознавалка документов»: вместо того чтобы клиент вручную
вписывал выручку и платежи, их считает система, а аналитик видит расчёт.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime


class StatementError(ValueError):
    pass


@dataclass
class Operation:
    day: date
    amount: float
    incoming: bool
    counterparty_inn: str | None
    counterparty: str
    purpose: str


LOAN_IN_RE = re.compile(r"(выдач|предоставлен)\w*\s.*(кредит|займ)", re.IGNORECASE)
LOAN_OUT_RE = re.compile(r"(погашен\w*|оплат\w*|уплат\w*)\s.*(кредит|займ)|процент\w*\s+по\s+(кредит|договор)", re.IGNORECASE)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise StatementError("Не удалось определить кодировку файла (ожидается UTF-8 или Windows-1251)")


def _parse_date(s: str) -> date:
    s = s.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise StatementError(f"Некорректная дата: {s!r}")


def _parse_amount(s: str) -> float:
    try:
        return float(s.replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError as e:
        raise StatementError(f"Некорректная сумма: {s!r}") from e


def parse_1c(text: str, company_inn: str) -> tuple[list[Operation], dict]:
    if not text.lstrip().startswith("1CClientBankExchange"):
        raise StatementError("Файл не похож на выгрузку 1С: нет заголовка 1CClientBankExchange")
    header: dict[str, str] = {}
    ops: list[Operation] = []
    doc: dict[str, str] | None = None
    in_account_section = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("СекцияДокумент"):
            doc = {}
            continue
        if line == "КонецДокумента":
            if doc is not None:
                ops.append(_op_from_1c(doc, company_inn, header.get("РасчСчет")))
            doc = None
            continue
        if line == "СекцияРасчСчет":
            in_account_section = True
            continue
        if line == "КонецРасчСчет":
            in_account_section = False
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if doc is not None:
            doc[k] = v
        elif not in_account_section:
            header.setdefault(k, v)
    if not ops:
        raise StatementError("В выписке нет операций (секций «СекцияДокумент»)")
    return ops, {"account": header.get("РасчСчет"), "date_from": header.get("ДатаНачала"), "date_to": header.get("ДатаКонца")}


def _op_from_1c(d: dict[str, str], company_inn: str, account: str | None) -> Operation:
    payer_inn = d.get("ПлательщикИНН") or None
    recv_inn = d.get("ПолучательИНН") or None
    recv_acc = d.get("ПолучательСчет")
    incoming = bool(d.get("ДатаПоступило")) or (account is not None and recv_acc == account) or (
        recv_inn == company_inn and payer_inn != company_inn)
    day_s = d.get("ДатаПоступило") or d.get("ДатаСписано") or d.get("Дата")
    if not day_s:
        raise StatementError("У операции нет даты")
    cp_inn = payer_inn if incoming else recv_inn
    cp_name = (d.get("Плательщик") if incoming else d.get("Получатель")) or d.get("Плательщик1") or ""
    return Operation(_parse_date(day_s), _parse_amount(d.get("Сумма", "0")), incoming, cp_inn, cp_name,
                     d.get("НазначениеПлатежа", ""))


def parse_csv(text: str) -> list[Operation]:
    sample = text[:2000]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    required = {"date", "amount", "direction"}
    if not reader.fieldnames or not required <= {f.strip().lower() for f in reader.fieldnames}:
        raise StatementError("CSV должен содержать колонки date;amount;direction[;counterparty_inn;counterparty;purpose]")
    ops = []
    for row in reader:
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        direction = r["direction"].lower()
        if direction not in ("in", "out", "приход", "расход"):
            raise StatementError(f"direction должен быть in/out, получено {r['direction']!r}")
        ops.append(Operation(_parse_date(r["date"]), _parse_amount(r["amount"]), direction in ("in", "приход"),
                             r.get("counterparty_inn") or None, r.get("counterparty", ""), r.get("purpose", "")))
    if not ops:
        raise StatementError("В CSV нет операций")
    return ops


def analyze(raw: bytes, company_inn: str) -> dict:
    text = _decode(raw)
    meta: dict = {}
    if text.lstrip().startswith("1CClientBankExchange"):
        ops, meta = parse_1c(text, company_inn)
        fmt = "1c"
    else:
        ops = parse_csv(text)
        fmt = "csv"

    own = loans_in = 0.0
    by_month_in: dict[str, float] = defaultdict(float)
    by_month_out: dict[str, float] = defaultdict(float)
    debt_out: dict[str, float] = defaultdict(float)
    payers: dict[str, float] = defaultdict(float)
    for op in ops:
        m = op.day.strftime("%Y-%m")
        by_month_in.setdefault(m, 0.0)
        if op.counterparty_inn and op.counterparty_inn == company_inn:
            own += op.amount
            continue
        if op.incoming:
            if LOAN_IN_RE.search(op.purpose):
                loans_in += op.amount
                continue
            by_month_in[m] += op.amount
            payers[op.counterparty_inn or op.counterparty or "?"] += op.amount
        else:
            by_month_out[m] += op.amount
            if LOAN_OUT_RE.search(op.purpose):
                debt_out[m] += op.amount

    months = sorted(set(by_month_in) | set(by_month_out))
    incoming = [by_month_in.get(m, 0.0) for m in months]
    n = len(months)
    avg_in = sum(incoming) / n if n else 0.0
    cv = (statistics.pstdev(incoming) / avg_in) if n > 1 and avg_in > 0 else None
    total_in = sum(incoming)
    top_share = (max(payers.values()) / total_in) if payers and total_in > 0 else None
    trend = None
    if n >= 6:
        last3, prev3 = sum(incoming[-3:]) / 3, sum(incoming[-6:-3]) / 3
        trend = (last3 / prev3 - 1) if prev3 > 0 else None
    warnings = []
    if n < 6:
        warnings.append(f"Выписка покрывает только {n} мес. — для оценки нужно не менее 6")
    if top_share is not None and top_share > 0.5:
        warnings.append(f"Высокая зависимость от одного покупателя: {top_share:.0%} поступлений")
    if cv is not None and cv > 0.5:
        warnings.append("Сильные колебания поступлений по месяцам")
    if loans_in > 0:
        warnings.append("Из оборотов исключены поступления кредитов и займов")
    if own > 0:
        warnings.append("Из оборотов исключены переводы между собственными счетами")

    return {
        "format": fmt,
        "account": meta.get("account"),
        "period": {"from": min(op.day for op in ops).isoformat(), "to": max(op.day for op in ops).isoformat()},
        "operations": len(ops),
        "months_covered": n,
        "months": [{"month": m, "incoming": round(by_month_in.get(m, 0.0), 2), "outgoing": round(by_month_out.get(m, 0.0), 2)} for m in months],
        "avg_monthly_incoming": round(avg_in, 2),
        "annualized_revenue": round(avg_in * 12, 2),
        "turnover_volatility": round(cv, 4) if cv is not None else None,
        "debt_payments_monthly": round(sum(debt_out.values()) / n, 2) if n else 0.0,
        "own_transfers_excluded": round(own, 2),
        "loan_proceeds_excluded": round(loans_in, 2),
        "top_payer_share": round(top_share, 4) if top_share is not None else None,
        "payers_count": len(payers),
        "trend_3m": round(trend, 4) if trend is not None else None,
        "warnings": warnings,
    }
