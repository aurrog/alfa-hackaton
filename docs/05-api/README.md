# 05. API

| Артефакт | Где |
|---|---|
| Swagger UI (на запущенном стенде) | http://localhost:8080/api/docs |
| Спецификация OpenAPI 3.1 | [openapi.json](openapi.json), [openapi.yaml](openapi.yaml) — генерируются из кода (`backend/scripts/gen_docs.py`), CI проверяет актуальность |
| Коллекция Postman | [postman_collection.json](postman_collection.json): сценарии S1 и S2 с проверками + все методы |
| Запросы для REST Client (VS Code / JetBrains) | [requests.http](requests.http) |
| Симулятор внешних систем | http://localhost:8081/docs |

## Соглашения

- **Базовый адрес** — `/api/v1`; версия в пути, несовместимые изменения — новая версия.
- **Аутентификация** — `POST /api/v1/auth/login` → `access_token`; далее заголовок `Authorization: Bearer <token>`.
  Тестовые учётки — `GET /api/v1/auth/demo-accounts` (при `DEMO_MODE=true`), пароль `Demo-2026`.
- **Ошибки** — RFC 7807, `Content-Type: application/problem+json`:

  ```json
  {"type": "https://errors.credit-cabinet.local/authority_exceeded", "title": "Доступ запрещён", "status": 403,
   "detail": "Решение требует уровня «Кредитный комитет» — вынесите заявку на кредитный комитет",
   "code": "authority_exceeded", "request_id": "4f1c…"}
  ```

  Ошибки валидации дополнительно содержат `errors: [{field, message}]`. Основные коды: `validation_failed` (422),
  `unauthorized` / `token_expired` (401), `forbidden`, `signer_required`, `authority_exceeded` (403), `not_found` (404),
  `invalid_transition`, `stale_version`, `conflict` (409), `too_many_attempts` (429).
- **Идемпотентность** — `submit`, `offer/accept`, `contract/sign` принимают `Idempotency-Key` (до 100 символов).
  Повтор с тем же ключом не выполняет действие повторно и возвращает сохранённый ответ с заголовком
  `Idempotent-Replayed: true`; тот же ключ для другого запроса — 422 `idempotency_key_reused`. Интерфейс генерирует ключ сам.
- **Конкурентность** — заявка версионируется (`version`); параллельное изменение → 409 `stale_version`. Решение банка
  принимает `version`, которую видел сотрудник, — решение по устаревшим данным невозможно.
- **Трассировка** — `X-Request-ID` принимается (или генерируется nginx/API), возвращается в ответе и попадает в журналы
  API, воркера и симулятора.
- **Время** — ISO 8601 с часовым поясом (UTC); деньги — числа в рублях; ставки — проценты годовых.
- **Статусы** — коды и подписи для клиента и банка: `GET /api/v1/meta/state-machine`;
  справочники — `GET /api/v1/meta/dictionaries`.
- **Обновление статуса** — опрос `GET /api/v1/applications/{id}` (интерфейс: 1 с во время конвейера, 4 с — у банка).

## Методы

### Аутентификация и служебные

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/auth/login` | Вход, токен |
| POST | `/auth/logout` | Выход (аудит) |
| GET | `/auth/me` | Пользователь и его компании с ролями |
| GET | `/auth/demo-accounts` | Тестовые учётки (DEMO_MODE) |
| GET | `/meta/state-machine`, `/meta/dictionaries` | Статусы, переходы, справочники |
| GET | `/api/health/live`, `/api/health/ready` | Проверки здоровья |

### Кабинет клиента

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/companies` | Подключить компанию по ИНН (ЕГРЮЛ/ЕГРИП) |
| GET | `/companies/{id}` | Карточка, предодобренные предложения, сводка |
| GET | `/products?company_id=` | Каталог с доступностью для компании |
| POST | `/products/recommend` | Подбор под задачу: «почему подходит», «что помешает», платёж |
| POST | `/calculator` | Платёж, переплата, эффективная ставка, график |
| GET / POST | `/applications` | Список заявок / черновик с автозаполнением |
| GET / PATCH | `/applications/{id}` | Заявка целиком (маршрут, анкета, источники полей, чек-лист, задачи, предложение, объяснение) / автосохранение |
| POST / DELETE / GET | `/applications/{id}/documents[/{doc}][/file]` | Документы; выписка 1С/CSV разбирается автоматически |
| POST | `/applications/{id}/send-for-signature`, `/return-to-draft` | Передача на подпись руководителю и обратно |
| POST | `/applications/{id}/submit` | ПЭП: заявка и согласия → в банк (идемпотентно) |
| POST | `/applications/{id}/tasks/{task}/answer`, `/resume` | Уточнения по запросу банка |
| POST | `/applications/{id}/offer/accept`, `/offer/decline` | Решение по предложению |
| GET / POST | `/applications/{id}/contract`, `/contract/sign` | Договор (HTML) и его подпись |
| POST | `/applications/{id}/cancel` | Отзыв заявки |
| GET | `/loans` | Кредиты и графики |
| GET / POST | `/notifications`, `/notifications/{id}/read`, `/notifications/read-all` | Уведомления в кабинете |
| GET / POST / PUT | `/feed`, `/feed/actions`, `/feed/topics` | Персональная лента, реакции, темы |
| POST | `/assistant` | Помощник (база знаний + данные заявки) |
| GET | `/demo/sample-statement/{company_id}` | Демо-выписка 1С (DEMO_MODE) |

### Рабочее место банка

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/bank/queue?status=&assigned=&product=&search=` | Очередь с нормативами, грейдом и рекомендацией |
| GET | `/bank/applications/{id}` | Досье: источники, проверки, скоринг, рекомендация, расчёт посильности, журнал, доступные действия |
| POST | `/bank/applications/{id}/assign` | Взять в работу |
| POST | `/bank/applications/{id}/decision` | `approve` · `decline` · `request_info` · `escalate` · `rerun` · `return` |
| GET | `/bank/applications/{id}/memo` | Черновик кредитного заключения |
| POST / GET | `/bank/documents/{id}/review`, `/bank/documents/{id}/file` | Проверка и скачивание документов |
| GET | `/bank/dashboard?days=` | Метрики процесса |
| GET / POST | `/bank/policy` | Действующая политика и история / новая версия |
| GET | `/bank/audit` | Журнал аудита |
| GET / POST | `/bank/system`, `/bank/jobs/{id}/retry` | Мониторинг очереди задач, повтор неуспешной задачи |

Пример решения аналитика:

```http
POST /api/v1/bank/applications/{id}/decision
Authorization: Bearer …
Content-Type: application/json

{"action": "approve", "amount": 4000000, "term_months": 36, "comment": "Обороты подтверждены выпиской", "version": 7}
```

## Симулятор внешних систем

| Метод | Путь | Что моделирует |
|---|---|---|
| GET | `/egrul/v1/entities/{inn}` | ЕГРЮЛ/ЕГРИП |
| GET | `/fns/v1/transparent-business/{inn}` | ФНС: выручка, налоговая задолженность, массовый адрес |
| GET | `/msp-registry/v1/{inn}` | Реестр МСП |
| POST | `/aml/v1/screening` | Стоп-листы |
| POST | `/bki/v1/credit-reports` | БКИ (без подписанного согласия — 422) |
| GET | `/abs/v1/clients/{inn}` | АБС: обороты, продукты (не клиент — 404) |
| POST | `/abs/v1/loans` | АБС: выдача (обязателен `Idempotency-Key`) |
| GET | `/samples/statements/{inn}` | Синтетическая выписка 1С |
| POST / GET / DELETE | `/admin/faults` | Сбои: `{"inn": "*", "source": "bki_company", "mode": "outage|error|timeout|slow", "seconds": 60}` |
| POST | `/admin/reset` | Сброс состояния (сбои, выданные кредиты) |
| GET | `/admin/calls`, `/admin/scenarios` | Последние вызовы, компании сценариев |

Любой корректный ИНН даёт детерминированный сгенерированный профиль; ИНН с префиксом `99` — «не найдено».
Заголовок `X-Mock-Latency: 0` отключает задержку.

## Запуск коллекции

```bash
npx newman@6 run docs/05-api/postman_collection.json --working-dir . \
  --folder "Сценарий S1: экспресс-кредит от заявки до выдачи"
```

Сценарии рассчитаны на исходные данные стенда; при повторных прогонах сбросьте симулятор
(`curl -X POST localhost:8081/admin/reset`) — у клиента после выдачи растёт долговая нагрузка, и условия меняются.
