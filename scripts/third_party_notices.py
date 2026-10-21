"""Сборка THIRD_PARTY_NOTICES.md: зависимости Python (из lock-файлов и метаданных пакетов),
npm (из package-lock.json), образы, шрифты, модели, данные и смоделированные интеграции.

    python scripts/third_party_notices.py            # нужен venv с установленным backend/requirements-dev.lock
"""

from __future__ import annotations

import json
import re
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lock_packages(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)==([^\s\\]+)", line)
        if m:
            out[m.group(1).split("[")[0].lower()] = m.group(2)
    return out


def py_license(name: str) -> str:
    try:
        md = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "см. PyPI"
    lic = md.get("License-Expression") or ""
    if not lic:
        lic = md.get("License") or ""
        if len(lic) > 60 or "\n" in lic:
            lic = ""
    if not lic:
        cls = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
        lic = ", ".join(cls)
    return lic or "см. PyPI"


def main() -> None:
    backend = lock_packages(ROOT / "backend" / "requirements.lock")
    dev = {k: v for k, v in lock_packages(ROOT / "backend" / "requirements-dev.lock").items() if k not in backend}
    mocks = lock_packages(ROOT / "mocks" / "requirements.lock")
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    npm = []
    for key, info in sorted(lock.get("packages", {}).items()):
        if not key.startswith("node_modules/"):
            continue
        name = key.split("node_modules/")[-1]
        npm.append((name, info.get("version", ""), info.get("license", "см. npm"), "сборка" if info.get("dev") else "приложение"))

    lines = [
        "# Сторонние компоненты, модели, данные и сервисы",
        "",
        "Файл собран скриптом `scripts/third_party_notices.py` из lock-файлов (версии зафиксированы, Python-пакеты — с хэшами).",
        "Все компоненты — с открытыми лицензиями и без оплаты; платные API, лицензии и сервисы не используются.",
        "",
        "## 1. Модели, данные, сервисы",
        "",
        "| Компонент | Назначение | Лицензия / условия |",
        "|---|---|---|",
        "| Скоринговая карта `sme-scorecard 1.0.0` | Оценка кредитного риска; построена в `ml/build_scorecard.py` на синтетических данных | Собственная разработка, MIT |",
        "| Синтетический датасет для обучения карты | Генерируется скриптом с фиксированным seed, в репозиторий не входит | Собственный, данные вымышлены |",
        "| Qwen2.5-1.5B-Instruct (необязательно, профиль `ai`) | Формулировки помощника и черновика заключения; факты — только из базы знаний и досье | Apache 2.0, открытые веса |",
        "| Ollama 0.6.8 (необязательно, профиль `ai`) | Локальный сервер LLM с OpenAI-совместимым API | MIT |",
        "| Контент ленты, учётные записи, компании, документы, выписки | Демонстрационные данные (`backend/app/seed`, `test-data`) | Синтетические, вымышлены |",
        "| Справочник ОКВЭД/отраслей, маржинальность, регионы | Упрощённые синтетические значения (`app/domain/okved.py`) | Собственные |",
        "",
        "Внешние облачные сервисы и SaaS не используются; стенд работает автономно после сборки.",
        "",
        "## 2. Смоделированные интеграции",
        "",
        "Реальные системы заменены симулятором `mocks/` с упрощёнными контрактами; персональные данные не запрашиваются.",
        "",
        "| Внешняя система | Что моделируется | Эндпоинт симулятора |",
        "|---|---|---|",
        "| ЕГРЮЛ/ЕГРИП (ФНС) | Реквизиты, статус, руководитель, учредители, ОКВЭД, адрес | `GET /egrul/v1/entities/{inn}` |",
        "| ФНС «Прозрачный бизнес» | Выручка, налоговая задолженность, массовый адрес, блокировки | `GET /fns/v1/transparent-business/{inn}` |",
        "| Единый реестр субъектов МСП | Наличие и категория | `GET /msp-registry/v1/{inn}` |",
        "| Перечни Росфинмониторинга, стоп-листы | Совпадения по компании и лицам | `POST /aml/v1/screening` |",
        "| Бюро кредитных историй | Кредитный отчёт компании и собственника; без согласия — отказ 422 | `POST /bki/v1/credit-reports` |",
        "| АБС банка | Обороты по счёту клиента, продукты; идемпотентная выдача кредита | `GET /abs/v1/clients/{inn}`, `POST /abs/v1/loans` |",
        "| Простая электронная подпись | Повторный ввод пароля, хэш документа, время, IP (внутри продукта) | — |",
        "",
        "## 3. Образы контейнеров",
        "",
        "| Образ | Назначение | Лицензия |",
        "|---|---|---|",
        "| `python:3.12.12-slim` | API, воркер, миграции, симулятор | PSF License (Python), Debian — свободные лицензии |",
        "| `node:22.22.0-alpine` | Только сборка интерфейса | MIT (Node.js) |",
        "| `nginx:1.28.0-alpine` | Веб-сервер и прокси | BSD-2-Clause |",
        "| `postgres:16.10-alpine` | База данных и очередь задач | PostgreSQL License |",
        "| `ollama/ollama:0.6.8` (необязательно) | Локальная LLM | MIT |",
        "",
        "## 4. Шрифты и иконки",
        "",
        "| Компонент | Лицензия |",
        "|---|---|",
        "| Onest (`@fontsource/onest`) | SIL Open Font License 1.1 |",
        "| Unbounded (`@fontsource/unbounded`) | SIL Open Font License 1.1 |",
        "| Tabler Icons (`@tabler/icons-react`) | MIT |",
        "| DejaVu Sans (только для генерации тестовых PDF) | Bitstream Vera / DejaVu License |",
        "",
        f"## 5. Python — бэкенд (`backend/requirements.lock`, {len(backend)} пакетов)",
        "",
        "| Пакет | Версия | Лицензия |",
        "|---|---|---|",
        *[f"| {n} | {v} | {py_license(n)} |" for n, v in sorted(backend.items())],
        "",
        f"## 6. Python — инструменты разработки (`backend/requirements-dev.lock`, дополнительно {len(dev)})",
        "",
        "| Пакет | Версия | Лицензия |",
        "|---|---|---|",
        *[f"| {n} | {v} | {py_license(n)} |" for n, v in sorted(dev.items())],
        "",
        "Офлайн-построение скоринговой карты (`ml/requirements.txt`): numpy, pandas, scikit-learn (BSD-3-Clause), matplotlib "
        "(PSF-based). Генерация тестовых PDF: reportlab (BSD).",
        "",
        f"## 7. Python — симулятор (`mocks/requirements.lock`, {len(mocks)} пакетов)",
        "",
        "Подмножество пакетов бэкенда: " + ", ".join(f"{n} {v}" for n, v in sorted(mocks.items())) + ".",
        "",
        f"## 8. npm — интерфейс (`frontend/package-lock.json`, {len(npm)} пакетов)",
        "",
        "| Пакет | Версия | Лицензия | Где используется |",
        "|---|---|---|---|",
        *[f"| {n} | {v} | {lic} | {scope} |" for n, v, lic, scope in npm],
        "",
    ]
    (ROOT / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"THIRD_PARTY_NOTICES.md: python {len(backend)}+{len(dev)}, npm {len(npm)}")


if __name__ == "__main__":
    main()
