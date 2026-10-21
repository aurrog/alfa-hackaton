"""Синтетические тестовые файлы для сценариев (test-data/). Все данные вымышлены.

    pip install reportlab==4.* && python scripts/make_test_data.py

Документы — PDF с пометкой «синтетический документ»; выписки — из генератора
симулятора (тот же формат 1С, что выгружают банк-клиенты), CSV-пример и короткая выписка.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mocks"))
from simulator import fixtures  # noqa: E402
from simulator.statements import build_statement  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
pdfmetrics.registerFont(TTFont("DejaVu", FONT))
OUT = ROOT / "test-data"

DOCS = {
    "financial_statements_technostroy.pdf": ("Бухгалтерская отчётность ООО «ТехноСтрой» за 2025 год", [
        "Форма 1. Бухгалтерский баланс (тыс. руб.)", "Основные средства — 84 200", "Запасы — 31 600",
        "Дебиторская задолженность — 27 900", "Денежные средства — 6 300", "Капитал и резервы — 92 400",
        "Долгосрочные обязательства — 12 100", "Краткосрочные обязательства — 45 500", "",
        "Форма 2. Отчёт о финансовых результатах (тыс. руб.)", "Выручка — 198 000", "Себестоимость продаж — 163 900",
        "Прибыль от продаж — 21 700", "Чистая прибыль — 14 950"]),
    "collateral_egrn_technostroy.pdf": ("Выписка из ЕГРН (образец)", [
        "Объект: нежилое здание, производственный корпус", "Площадь: 2 400 кв. м",
        "Адрес: Московская область, г. Подольск, ул. Комсомольская, д. 1, стр. 5",
        "Правообладатель: ООО «ТехноСтрой», ИНН 5027841264", "Вид права: собственность",
        "Обременения: не зарегистрированы", "Оценочная стоимость (отчёт оценщика): 60 000 000 руб."]),
    "purchase_contract_technostroy.pdf": ("Договор поставки оборудования № 17/26", [
        "Поставщик: ООО «СтанкоИмпорт» (вымышленная компания)", "Покупатель: ООО «ТехноСтрой», ИНН 5027841264",
        "Предмет: обрабатывающий центр с ЧПУ, 2 единицы", "Цена договора: 46 800 000 руб., в т. ч. НДС",
        "Порядок оплаты: аванс 85% — за счёт кредитных средств, 15% — после пусконаладки",
        "Срок поставки: 90 календарных дней с даты оплаты аванса"]),
    "explanation_letter.pdf": ("Пояснительное письмо", [
        "Снижение поступлений в июле связано с сезонным характером спроса.",
        "В августе–сентябре поступления восстановились, подтверждается выпиской."]),
    "state_contract_example.pdf": ("Контракт № 0373200001226000123 (44-ФЗ) — образец", [
        "Заказчик: МБУ «Центр услуг» (вымышленная организация)", "Предмет: поставка компьютерной техники",
        "Цена контракта: 8 400 000 руб.", "Срок исполнения: до 31.12.2026"]),
}


def pdf(path: Path, title: str, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(title)
    w, h = A4
    c.setFont("DejaVu", 9)
    c.setFillGray(0.45)
    c.drawString(50, h - 40, "СИНТЕТИЧЕСКИЙ ДОКУМЕНТ ДЛЯ ДЕМОНСТРАЦИИ ПРОТОТИПА — НЕ ЯВЛЯЕТСЯ НАСТОЯЩИМ")
    c.setFillGray(0)
    c.setFont("DejaVu", 15)
    c.drawString(50, h - 80, title)
    c.setFont("DejaVu", 11)
    y = h - 115
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.setFont("DejaVu", 9)
    c.drawString(50, 60, f"Сформировано {date(2026, 10, 1).strftime('%d.%m.%Y')} генератором тестовых данных")
    c.save()


def main() -> None:
    (OUT / "documents").mkdir(parents=True, exist_ok=True)
    (OUT / "statements").mkdir(parents=True, exist_ok=True)
    for name, (title, lines) in DOCS.items():
        pdf(OUT / "documents" / name, title, lines)
    today = date(2026, 10, 21)
    fx = fixtures.build(today)
    for inn in ("5406732910", "5027841264"):
        text = build_statement(inn, fx[inn], today)
        (OUT / "statements" / f"kl_to_1c_{inn}.txt").write_bytes(text.encode("cp1251"))
    short = build_statement("5406732910", fx["5406732910"], today, months=3)
    (OUT / "statements" / "kl_to_1c_5406732910_3months.txt").write_bytes(short.encode("cp1251"))
    rows = ["date;amount;direction;counterparty_inn;counterparty;purpose"]
    for m in range(1, 13):
        y, mm = (2025, m + 9) if m <= 3 else (2026, m - 3)
        rows.append(f"{y}-{mm:02d}-10;{2_400_000 + m * 15_000};in;7701234560;ООО «Ромашка»;Оплата по договору")
        rows.append(f"{y}-{mm:02d}-15;{1_900_000 + m * 9_000};out;7711122233;ООО «Поставщик»;Оплата товара")
        rows.append(f"{y}-{mm:02d}-20;50000;out;7702070139;Банк;Погашение кредита по договору 5-К")
    (OUT / "statements" / "statement_example.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("готово:", *sorted(p.relative_to(ROOT).as_posix() for p in OUT.rglob("*.*") if p.suffix != ".md"), sep="\n  ")


if __name__ == "__main__":
    main()
