"""Генерация документации из кода — чтобы она не расходилась с реализацией.

    python scripts/gen_docs.py           # записать файлы в docs/
    python scripts/gen_docs.py --check   # проверить, что docs/ актуальны (CI)

Создаёт: диаграмму состояний (02-process/state-diagram.md), спецификацию OpenAPI
(05-api/openapi.json, openapi.yaml), коллекцию Postman со сценариями S1 и S2
(05-api/postman_collection.json), ER-диаграмму и описание таблиц (06-data-model/er-diagram.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain.state_machine import TRANSITIONS  # noqa: E402
from app.domain.statuses import STATUS_META, AppStatus  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

DOCS = ROOT / "docs"
ACTOR_RU = {"client": "клиент", "client_signer": "подписант клиента", "system": "система", "analyst": "аналитик",
            "committee": "комитет"}


# ------------------------------------------------------------------ машина состояний
def state_diagram() -> str:
    lines = ["# Диаграмма состояний кредитной заявки", "",
             "> Файл сгенерирован `backend/scripts/gen_docs.py` из `app/domain/state_machine.py` и `app/domain/statuses.py`.",
             "> Любое изменение статуса в системе проходит только по этим переходам.", "",
             f"Статусов: **{len(AppStatus)}**, переходов: **{len(TRANSITIONS)}**.", "", "```mermaid", "stateDiagram-v2",
             "    direction LR", "    [*] --> draft"]
    for s, m in STATUS_META.items():
        lines.append(f"    {s.value}: {m.label}")
    for t in TRANSITIONS:
        for src in sorted(t.sources, key=lambda x: list(AppStatus).index(x)):
            lines.append(f"    {src.value} --> {t.target.value}: {t.name}")
    for s, m in STATUS_META.items():
        if m.terminal:
            lines.append(f"    {s.value} --> [*]")
    lines += ["```", "", "## Статусы", "", "| Код | Для банка | Для клиента | Шаг маршрута | Чей ход | Норматив, ч | Конечный |",
              "|---|---|---|---|---|---|---|"]
    waiting = {"client": "клиент", "bank": "банк", "system": "система", "none": "—"}
    for s, m in STATUS_META.items():
        lines.append(f"| `{s.value}` | {m.label} | {m.client_label} | {m.stage} | {waiting[m.waiting.value]} | "
                     f"{m.sla_hours if m.sla_hours else '—'} | {'да' if m.terminal else ''} |")
    lines += ["", "## Переходы", "", "| Переход | Из | В | Кто выполняет | Событие в журнале |", "|---|---|---|---|---|"]
    for t in TRANSITIONS:
        src = ", ".join(f"`{x.value}`" for x in sorted(t.sources, key=lambda x: list(AppStatus).index(x)))
        who = ", ".join(ACTOR_RU[a.value] for a in sorted(t.actors, key=lambda a: a.value))
        lines.append(f"| `{t.name}` | {src} | `{t.target.value}` | {who} | {t.title} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ модель данных
TABLE_RU = {
    "users": "Пользователи: клиенты и сотрудники банка (роль, лимит полномочий)",
    "companies": "Компании клиентов: реквизиты из ЕГРЮЛ/ЕГРИП, признак клиента банка",
    "company_members": "Участники компании и их права (роль, право подписи, собственник-поручитель)",
    "products": "Кредитные продукты и их условия",
    "credit_policies": "Версии кредитной политики (параметры решения)",
    "applications": "Кредитные заявки: статус, анкета, источники автозаполнения, обогащение, грейд",
    "application_events": "Журнал событий заявки (переходы статусов, действия, интеграции)",
    "documents": "Документы заявки (метаданные; файлы — в хранилище)",
    "tasks": "Запросы информации у клиента (документ или вопрос)",
    "integration_calls": "Журнал вызовов внешних источников (попытка, длительность, ответ)",
    "check_results": "Результаты проверок полноты данных и кредитной политики",
    "scoring_results": "Результаты скоринга: балл, PD, грейд, вклад факторов",
    "decisions": "Рекомендации движка и итоговые решения (уровень полномочий, версии политики и модели)",
    "offers": "Кредитные предложения клиенту",
    "signatures": "Простые электронные подписи (хэш документа, подписант, время, IP)",
    "loans": "Выданные кредиты и графики платежей",
    "jobs": "Очередь задач конвейера (transactional outbox, повторы, аренда)",
    "notifications": "Уведомления в кабинете",
    "news_items": "Материалы персональной ленты с параметрами аудитории",
    "feed_interactions": "Реакции пользователей на ленту",
    "feed_preferences": "Выбранные темы и выученные интересы",
    "audit_log": "Журнал аудита безопасности",
    "idempotency_keys": "Ключи идемпотентности и сохранённые ответы",
    "sequences": "Счётчики человекочитаемых номеров",
}


def er_diagram() -> str:
    tables = Base.metadata.sorted_tables
    lines = ["# Модель данных", "", "> Файл сгенерирован `backend/scripts/gen_docs.py` из `app/models.py` (SQLAlchemy). "
             "Схема создаётся миграциями Alembic (`backend/alembic`).", "", f"Таблиц: **{len(tables)}** (PostgreSQL 16).", "",
             "```mermaid", "erDiagram"]
    for t in tables:
        lines.append(f"    {t.name} {{")
        for c in t.columns:
            typ = type(c.type).__name__.lower().replace("uuid", "uuid")
            key = "PK" if c.primary_key else ("FK" if c.foreign_keys else "")
            lines.append(f"        {typ} {c.name} {key}".rstrip())
        lines.append("    }")
    rels = set()
    for t in tables:
        for c in t.columns:
            for fk in c.foreign_keys:
                parent = fk.column.table.name
                if parent != t.name:
                    rels.add((parent, t.name, c.name))
    for parent, child, col in sorted(rels):
        lines.append(f'    {parent} ||--o{{ {child} : "{col}"')
    lines += ["```", "", "## Таблицы", ""]
    for t in tables:
        lines += [f"### `{t.name}`", "", TABLE_RU.get(t.name, ""), "", "| Поле | Тип | Обязательное | Ключ/связь |", "|---|---|---|---|"]
        for c in t.columns:
            rel = "PK" if c.primary_key else ", ".join(f"→ {fk.column.table.name}.{fk.column.name}" for fk in c.foreign_keys)
            if c.unique:
                rel = (rel + ", " if rel else "") + "уникальное"
            lines.append(f"| `{c.name}` | {c.type} | {'да' if not c.nullable else ''} | {rel} |")
        idx = sorted(t.indexes, key=lambda i: i.name or "")
        if idx:
            lines.append("")
            lines.append("Индексы: " + ", ".join(f"`{i.name}` ({', '.join(c.name for c in i.columns)})" for i in idx))
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ коллекция Postman
def _req(name, method, path, body=None, tests=None, pre=None, auth=True, form=None, headers=None):
    h = [{"key": "Content-Type", "value": "application/json"}] if body is not None else []
    if auth:
        h.append({"key": "Authorization", "value": "Bearer {{token}}"})
    for k, v in (headers or {}).items():
        h.append({"key": k, "value": v})
    item = {"name": name, "request": {"method": method, "header": h,
                                      "url": {"raw": "{{base}}" + path, "host": ["{{base}}"], "path": [p for p in path.split("?")[0].split("/") if p]}}}
    if "?" in path:
        item["request"]["url"]["query"] = [{"key": kv.split("=")[0], "value": kv.split("=")[1]} for kv in path.split("?")[1].split("&")]
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2)}
    if form is not None:
        item["request"]["body"] = {"mode": "formdata", "formdata": form}
    events = []
    if pre:
        events.append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre}})
    if tests:
        events.append({"listen": "test", "script": {"type": "text/javascript", "exec": tests}})
    if events:
        item["event"] = events
    return item


def _login(email):
    return _req(f"Вход: {email}", "POST", "/api/v1/auth/login", {"email": email, "password": "{{password}}"}, auth=False, tests=[
        "pm.test('вход выполнен', () => pm.response.to.have.status(200));",
        "pm.collectionVariables.set('token', pm.response.json().access_token);"])


def _me():
    return _req("Профиль и компания", "GET", "/api/v1/auth/me", tests=[
        "const me = pm.response.json();", "pm.test('есть компания', () => pm.expect(me.companies.length).to.be.above(0));",
        "pm.collectionVariables.set('company_id', me.companies[0].id);"])


def _wait(name, statuses, bank=False):
    path = "/api/v1/bank/applications/{{app_id}}" if bank else "/api/v1/applications/{{app_id}}"
    getter = "pm.response.json().application.status" if bank else "pm.response.json().status"
    return _req(name, "GET", path, pre=["setTimeout(() => {}, 1500);"], tests=[
        f"const st = {getter};", f"const target = {json.dumps(statuses)};",
        "const n = Number(pm.collectionVariables.get('poll') || 0);",
        "if (!target.includes(st) && n < 60) { pm.collectionVariables.set('poll', n + 1); postman.setNextRequest(pm.info.requestName); }",
        "else { pm.collectionVariables.set('poll', 0); pm.test('статус ' + target.join('|'), () => pm.expect(target).to.include(st)); }"])


def _submit(key):
    return _req("Подписать (ПЭП) и отправить в банк", "POST", "/api/v1/applications/{{app_id}}/submit",
                {"password": "{{password}}", "consent_bki": True, "consent_pd": True}, headers={"Idempotency-Key": key},
                tests=["pm.test('отправлено', () => pm.expect(pm.response.json().status).to.eql('submitted'));"])


def postman(spec: dict) -> dict:
    s1 = [
        _login("anna@kofe.test"), _me(),
        _req("Подбор продукта", "POST", "/api/v1/products/recommend",
             {"company_id": "{{company_id}}", "purpose": "equipment", "amount": 1500000, "term_months": 24, "urgent": True},
             tests=["pm.test('лучший — экспресс-кредит', () => pm.expect(pm.response.json().items[0].code).to.eql('EXPRESS'));"]),
        _req("Создать черновик (автозаполнение)", "POST", "/api/v1/applications",
             {"company_id": "{{company_id}}", "product_code": "EXPRESS", "amount": 1500000, "term_months": 24, "purpose": "equipment"},
             tests=["const a = pm.response.json();", "pm.test('черновик', () => pm.expect(a.status).to.eql('draft'));",
                    "pm.test('выручка подставлена', () => pm.expect(a.form.financials.monthly_revenue).to.be.above(0));",
                    "pm.collectionVariables.set('app_id', a.id);"]),
        _submit("{{$guid}}"),
        _wait("Ждём решение конвейера", ["offer_issued"]),
        _req("Предложение", "GET", "/api/v1/applications/{{app_id}}", tests=[
            "const o = pm.response.json().offer;", "pm.test('1 500 000 ₽ на 24 мес. под 21,5%', () => {",
            "  pm.expect(o.amount).to.eql(1500000); pm.expect(o.term_months).to.eql(24); pm.expect(o.rate).to.eql(21.5); });"]),
        _req("Принять предложение", "POST", "/api/v1/applications/{{app_id}}/offer/accept", headers={"Idempotency-Key": "{{$guid}}"},
             tests=["pm.test('принято', () => pm.expect(pm.response.json().status).to.eql('offer_accepted'));"]),
        _req("Подписать договор", "POST", "/api/v1/applications/{{app_id}}/contract/sign", {"password": "{{password}}"},
             headers={"Idempotency-Key": "{{$guid}}"}, tests=["pm.test('выдача', () => pm.expect(pm.response.json().status).to.eql('disbursement'));"]),
        _wait("Ждём выдачу", ["issued"]),
    ]
    docs = [("financial_statements", "financial_statements_technostroy.pdf"), ("collateral_docs", "collateral_egrn_technostroy.pdf"),
            ("purchase_contract", "purchase_contract_technostroy.pdf")]
    s2 = [
        _login("irina@technostroy.test"), _me(),
        _req("Создать заявку на 40 млн ₽", "POST", "/api/v1/applications",
             {"company_id": "{{company_id}}", "product_code": "INVEST", "amount": 40000000, "term_months": 60, "purpose": "equipment"},
             tests=["pm.collectionVariables.set('app_id', pm.response.json().id);"]),
        _req("Указать залог", "PATCH", "/api/v1/applications/{{app_id}}",
             {"collateral": {"type": "real_estate", "value": 60000000, "description": "Производственный корпус"}}),
        *[_req(f"Загрузить: {dt}", "POST", "/api/v1/applications/{{app_id}}/documents",
               form=[{"key": "doc_type", "value": dt, "type": "text"}, {"key": "file", "type": "file", "src": f"test-data/documents/{fn}"}],
               tests=["pm.test('загружено', () => pm.response.to.have.status(201));"]) for dt, fn in docs],
        _req("Бухгалтер не может подписать", "POST", "/api/v1/applications/{{app_id}}/submit",
             {"password": "{{password}}", "consent_bki": True, "consent_pd": True},
             tests=["pm.test('403 signer_required', () => pm.expect(pm.response.json().code).to.eql('signer_required'));"]),
        _req("Передать на подпись", "POST", "/api/v1/applications/{{app_id}}/send-for-signature",
             tests=["pm.test('ждёт подписи', () => pm.expect(pm.response.json().status).to.eql('pending_signature'));"]),
        _login("oleg@technostroy.test"), _submit("{{$guid}}"),
        _wait("Ждём передачу специалисту", ["manual_review"]),
        _login("analyst@bank.test"),
        _req("Досье", "GET", "/api/v1/bank/applications/{{app_id}}", tests=[
            "const d = pm.response.json();", "pm.test('рекомендация — одобрить', () => pm.expect(d.recommendation.outcome).to.eql('approve'));",
            "pm.collectionVariables.set('version', d.application.version);"]),
        _req("Одобрить сверх полномочий — отказ", "POST", "/api/v1/bank/applications/{{app_id}}/decision", {"action": "approve"},
             tests=["pm.test('403 authority_exceeded', () => pm.expect(pm.response.json().code).to.eql('authority_exceeded'));"]),
        _req("Вынести на кредитный комитет", "POST", "/api/v1/bank/applications/{{app_id}}/decision",
             {"action": "escalate", "comment": "Сумма выше полномочий аналитика"},
             tests=["pm.test('на комитете', () => pm.expect(pm.response.json().application.status).to.eql('committee_review'));"]),
        _login("risk@bank.test"),
        _req("Решение комитета: одобрить", "POST", "/api/v1/bank/applications/{{app_id}}/decision", {"action": "approve", "comment": "Одобрено"},
             tests=["pm.test('предложение', () => pm.expect(pm.response.json().application.status).to.eql('offer_issued'));"]),
        _login("oleg@technostroy.test"),
        _req("Предложение директору", "GET", "/api/v1/applications/{{app_id}}", tests=[
            "const o = pm.response.json().offer;", "pm.test('40 млн ₽, 60 мес., 18,5%', () => {",
            "  pm.expect(o.amount).to.eql(40000000); pm.expect(o.term_months).to.eql(60); pm.expect(o.rate).to.eql(18.5); });"]),
    ]
    # справочник всех методов по OpenAPI
    by_tag: dict[str, list] = {}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            tag = (op.get("tags") or ["Прочее"])[0]
            p = path.replace("{", "{{").replace("}", "}}")
            by_tag.setdefault(tag, []).append(_req(f"{method.upper()} {path} — {op.get('summary', '')}", method.upper(), p,
                                                   body={} if method in ("post", "patch", "put") and "requestBody" in op and "multipart" not in json.dumps(op["requestBody"]) else None,
                                                   auth=not path.startswith("/api/health")))
    return {
        "info": {"name": "Умный кредитный кабинет — API", "_postman_id": "8a5c7d4e-2f61-4c7b-9a1e-credit-cabinet",
                 "description": "Сценарии S1 и S2 проходят путь заявки целиком; папка «Все методы» сгенерирована из OpenAPI.",
                 "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "variable": [{"key": "base", "value": "http://localhost:8080"}, {"key": "password", "value": "Demo-2026"},
                     {"key": "token", "value": ""}, {"key": "company_id", "value": ""}, {"key": "app_id", "value": ""},
                     {"key": "version", "value": ""}, {"key": "poll", "value": "0"}],
        "item": [
            {"name": "Сценарий S1: экспресс-кредит от заявки до выдачи", "item": s1},
            {"name": "Сценарий S2: бухгалтер → директор → аналитик → комитет", "item": s2},
            {"name": "Все методы", "item": [{"name": t, "item": items} for t, items in by_tag.items()]},
        ],
    }


def build() -> dict[Path, str]:
    spec = app.openapi()
    return {
        DOCS / "02-process" / "state-diagram.md": state_diagram(),
        DOCS / "05-api" / "openapi.json": json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        DOCS / "05-api" / "openapi.yaml": yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120),
        DOCS / "05-api" / "postman_collection.json": json.dumps(postman(spec), ensure_ascii=False, indent=2) + "\n",
        DOCS / "06-data-model" / "er-diagram.md": er_diagram(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="не записывать, а проверить актуальность")
    args = ap.parse_args()
    stale = []
    for path, content in build().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"записан {path.relative_to(ROOT)}")
    if stale:
        print("Документация устарела, выполните `python backend/scripts/gen_docs.py`:", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
