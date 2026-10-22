# Сторонние компоненты, модели, данные и сервисы

Файл собран скриптом `scripts/third_party_notices.py` из lock-файлов (версии зафиксированы, Python-пакеты — с хэшами).
Все компоненты — с открытыми лицензиями и без оплаты; платные API, лицензии и сервисы не используются.

## 1. Модели, данные, сервисы

| Компонент | Назначение | Лицензия / условия |
|---|---|---|
| Скоринговая карта `sme-scorecard 1.0.0` | Оценка кредитного риска; построена в `ml/build_scorecard.py` на синтетических данных | Собственная разработка, MIT |
| Синтетический датасет для обучения карты | Генерируется скриптом с фиксированным seed, в репозиторий не входит | Собственный, данные вымышлены |
| Qwen2.5-1.5B-Instruct (необязательно, профиль `ai`) | Формулировки помощника и черновика заключения; факты — только из базы знаний и досье | Apache 2.0, открытые веса |
| Ollama 0.6.8 (необязательно, профиль `ai`) | Локальный сервер LLM с OpenAI-совместимым API | MIT |
| Контент ленты, учётные записи, компании, документы, выписки | Демонстрационные данные (`backend/app/seed`, `test-data`) | Синтетические, вымышлены |
| Справочник ОКВЭД/отраслей, маржинальность, регионы | Упрощённые синтетические значения (`app/domain/okved.py`) | Собственные |

Внешние облачные сервисы и SaaS не используются; стенд работает автономно после сборки.

## 2. Смоделированные интеграции

Реальные системы заменены симулятором `mocks/` с упрощёнными контрактами; персональные данные не запрашиваются.

| Внешняя система | Что моделируется | Эндпоинт симулятора |
|---|---|---|
| ЕГРЮЛ/ЕГРИП (ФНС) | Реквизиты, статус, руководитель, учредители, ОКВЭД, адрес | `GET /egrul/v1/entities/{inn}` |
| ФНС «Прозрачный бизнес» | Выручка, налоговая задолженность, массовый адрес, блокировки | `GET /fns/v1/transparent-business/{inn}` |
| Единый реестр субъектов МСП | Наличие и категория | `GET /msp-registry/v1/{inn}` |
| Перечни Росфинмониторинга, стоп-листы | Совпадения по компании и лицам | `POST /aml/v1/screening` |
| Бюро кредитных историй | Кредитный отчёт компании и собственника; без согласия — отказ 422 | `POST /bki/v1/credit-reports` |
| АБС банка | Обороты по счёту клиента, продукты; идемпотентная выдача кредита | `GET /abs/v1/clients/{inn}`, `POST /abs/v1/loans` |
| Простая электронная подпись | Повторный ввод пароля, хэш документа, время, IP (внутри продукта) | — |

## 3. Образы контейнеров

| Образ | Назначение | Лицензия |
|---|---|---|
| `python:3.12.12-slim` | API, воркер, миграции, симулятор | PSF License (Python), Debian — свободные лицензии |
| `node:22.22.0-alpine` | Только сборка интерфейса | MIT (Node.js) |
| `nginx:1.28.0-alpine` | Веб-сервер и прокси | BSD-2-Clause |
| `postgres:16.10-alpine` | База данных и очередь задач | PostgreSQL License |
| `ollama/ollama:0.6.8` (необязательно) | Локальная LLM | MIT |

## 4. Шрифты и иконки

| Компонент | Лицензия |
|---|---|
| Onest (`@fontsource/onest`) | SIL Open Font License 1.1 |
| Unbounded (`@fontsource/unbounded`) | SIL Open Font License 1.1 |
| Tabler Icons (`@tabler/icons-react`) | MIT |
| DejaVu Sans (только для генерации тестовых PDF) | Bitstream Vera / DejaVu License |

## 5. Python — бэкенд (`backend/requirements.lock`, 40 пакетов)

| Пакет | Версия | Лицензия |
|---|---|---|
| alembic | 1.20.0 | MIT |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| argon2-cffi | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| certifi | 2026.10.19 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| fastapi | 0.157.0 | MIT |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httptools | 0.9.0 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD License |
| mako | 1.4.3 | MIT |
| markupsafe | 3.0.4 | BSD-3-Clause |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| prometheus-client | 0.26.0 | Apache-2.0 AND BSD-2-Clause |
| psycopg | 3.3.6 | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| pydantic-core | 2.50.1 | MIT |
| pydantic-settings | 2.16.1 | MIT |
| pyjwt | 2.15.1 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| pyyaml | 6.0.3 | MIT |
| sqlalchemy | 2.0.55 | MIT |
| starlette | 1.9.0 | BSD-3-Clause |
| typing-extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| tzdata | 2026.5 | см. PyPI |
| uvicorn | 0.54.0 | BSD-3-Clause |
| uvloop | 0.23.0 | MIT License |
| watchfiles | 1.3.0 | MIT |
| websockets | 17.3 | BSD-3-Clause |

## 6. Python — инструменты разработки (`backend/requirements-dev.lock`, дополнительно 7)

| Пакет | Версия | Лицензия |
|---|---|---|
| colorama | 0.4.6 | см. PyPI |
| iniconfig | 2.3.1 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.1.1 | MIT |
| ruff | 0.17.1 | MIT |

Офлайн-построение скоринговой карты (`ml/requirements.txt`): numpy, pandas, scikit-learn (BSD-3-Clause), matplotlib (PSF-based). Генерация тестовых PDF: reportlab (BSD).

## 7. Python — симулятор (`mocks/requirements.lock`, 14 пакетов)

Подмножество пакетов бэкенда: annotated-doc 0.0.5, annotated-types 0.8.0, anyio 4.15.1, click 8.5.0, fastapi 0.157.0, h11 0.16.0, idna 3.20, opentelemetry-api 1.45.1, pydantic 2.14.1, pydantic-core 2.50.1, starlette 1.9.0, typing-extensions 4.16.0, typing-inspection 0.4.4, uvicorn 0.54.0.

## 8. npm — интерфейс (`frontend/package-lock.json`, 206 пакетов)

| Пакет | Версия | Лицензия | Где используется |
|---|---|---|---|
| @babel/code-frame | 7.29.7 | MIT | сборка |
| @babel/compat-data | 7.29.7 | MIT | сборка |
| @babel/core | 7.29.7 | MIT | сборка |
| @babel/generator | 7.29.8 | MIT | сборка |
| @babel/helper-compilation-targets | 7.29.7 | MIT | сборка |
| @babel/helper-globals | 7.29.7 | MIT | сборка |
| @babel/helper-module-imports | 7.29.7 | MIT | сборка |
| @babel/helper-module-transforms | 7.29.7 | MIT | сборка |
| @babel/helper-plugin-utils | 7.29.7 | MIT | сборка |
| @babel/helper-string-parser | 7.29.7 | MIT | сборка |
| @babel/helper-validator-identifier | 7.29.7 | MIT | сборка |
| @babel/helper-validator-option | 7.29.7 | MIT | сборка |
| @babel/helpers | 7.29.10 | MIT | сборка |
| @babel/parser | 7.29.9 | MIT | сборка |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | MIT | сборка |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | MIT | сборка |
| @babel/runtime | 7.29.10 | MIT | приложение |
| @babel/template | 7.29.7 | MIT | сборка |
| @babel/traverse | 7.29.10 | MIT | сборка |
| @babel/types | 7.29.8 | MIT | сборка |
| @esbuild/aix-ppc64 | 0.25.12 | MIT | сборка |
| @esbuild/android-arm | 0.25.12 | MIT | сборка |
| @esbuild/android-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/android-x64 | 0.25.12 | MIT | сборка |
| @esbuild/darwin-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/darwin-x64 | 0.25.12 | MIT | сборка |
| @esbuild/freebsd-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/freebsd-x64 | 0.25.12 | MIT | сборка |
| @esbuild/linux-arm | 0.25.12 | MIT | сборка |
| @esbuild/linux-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/linux-ia32 | 0.25.12 | MIT | сборка |
| @esbuild/linux-loong64 | 0.25.12 | MIT | сборка |
| @esbuild/linux-mips64el | 0.25.12 | MIT | сборка |
| @esbuild/linux-ppc64 | 0.25.12 | MIT | сборка |
| @esbuild/linux-riscv64 | 0.25.12 | MIT | сборка |
| @esbuild/linux-s390x | 0.25.12 | MIT | сборка |
| @esbuild/linux-x64 | 0.25.12 | MIT | сборка |
| @esbuild/netbsd-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/netbsd-x64 | 0.25.12 | MIT | сборка |
| @esbuild/openbsd-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/openbsd-x64 | 0.25.12 | MIT | сборка |
| @esbuild/openharmony-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/sunos-x64 | 0.25.12 | MIT | сборка |
| @esbuild/win32-arm64 | 0.25.12 | MIT | сборка |
| @esbuild/win32-ia32 | 0.25.12 | MIT | сборка |
| @esbuild/win32-x64 | 0.25.12 | MIT | сборка |
| @floating-ui/core | 1.8.0 | MIT | приложение |
| @floating-ui/dom | 1.8.0 | MIT | приложение |
| @floating-ui/react | 0.26.28 | MIT | приложение |
| @floating-ui/react-dom | 2.1.9 | MIT | приложение |
| @floating-ui/utils | 0.2.12 | MIT | приложение |
| @fontsource/onest | 5.3.1 | OFL-1.1 | приложение |
| @fontsource/unbounded | 5.3.0 | OFL-1.1 | приложение |
| @jridgewell/gen-mapping | 0.3.13 | MIT | сборка |
| @jridgewell/remapping | 2.3.5 | MIT | сборка |
| @jridgewell/resolve-uri | 3.1.2 | MIT | сборка |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | сборка |
| @jridgewell/trace-mapping | 0.3.31 | MIT | сборка |
| @mantine/core | 7.17.8 | MIT | приложение |
| @mantine/dropzone | 7.17.8 | MIT | приложение |
| @mantine/hooks | 7.17.8 | MIT | приложение |
| @mantine/notifications | 7.17.8 | MIT | приложение |
| @mantine/store | 7.17.8 | MIT | приложение |
| @napi-rs/lzma-linux-x64-gnu | 1.5.1 | MIT | сборка |
| @rolldown/pluginutils | 1.0.0-beta.27 | MIT | сборка |
| @rollup/rollup-android-arm-eabi | 4.64.12 | MIT | сборка |
| @rollup/rollup-android-arm64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-darwin-arm64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-darwin-x64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-freebsd-arm64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-freebsd-x64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-arm-gnueabihf | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-arm-musleabihf | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-arm64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-arm64-musl | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-loong64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-loong64-musl | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-ppc64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-ppc64-musl | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-riscv64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-riscv64-musl | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-s390x-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-x64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-linux-x64-musl | 4.64.12 | MIT | сборка |
| @rollup/rollup-openbsd-x64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-openharmony-arm64 | 4.64.12 | MIT | сборка |
| @rollup/rollup-win32-arm64-msvc | 4.64.12 | MIT | сборка |
| @rollup/rollup-win32-ia32-msvc | 4.64.12 | MIT | сборка |
| @rollup/rollup-win32-x64-gnu | 4.64.12 | MIT | сборка |
| @rollup/rollup-win32-x64-msvc | 4.64.12 | MIT | сборка |
| @tabler/icons | 3.49.0 | MIT | приложение |
| @tabler/icons-react | 3.49.0 | MIT | приложение |
| @tanstack/query-core | 5.104.5 | MIT | приложение |
| @tanstack/react-query | 5.104.5 | MIT | приложение |
| @types/babel__core | 7.20.5 | MIT | сборка |
| @types/babel__generator | 7.27.0 | MIT | сборка |
| @types/babel__template | 7.4.4 | MIT | сборка |
| @types/babel__traverse | 7.28.0 | MIT | сборка |
| @types/d3-array | 3.2.2 | MIT | приложение |
| @types/d3-color | 3.1.3 | MIT | приложение |
| @types/d3-ease | 3.0.2 | MIT | приложение |
| @types/d3-interpolate | 3.0.4 | MIT | приложение |
| @types/d3-path | 3.1.1 | MIT | приложение |
| @types/d3-scale | 4.0.9 | MIT | приложение |
| @types/d3-shape | 3.2.0 | MIT | приложение |
| @types/d3-time | 3.0.4 | MIT | приложение |
| @types/d3-timer | 3.0.2 | MIT | приложение |
| @types/estree | 1.0.9 | MIT | сборка |
| @types/prop-types | 15.7.15 | MIT | приложение |
| @types/react | 18.3.31 | MIT | приложение |
| @types/react-dom | 18.3.7 | MIT | сборка |
| @vitejs/plugin-react | 4.7.0 | MIT | сборка |
| baseline-browser-mapping | 2.11.30 | Apache-2.0 | сборка |
| browserslist | 4.29.4 | MIT | сборка |
| camelcase-css | 2.0.1 | MIT | сборка |
| caniuse-lite | 1.0.30001818 | CC-BY-4.0 | сборка |
| clsx | 2.1.1 | MIT | приложение |
| convert-source-map | 2.0.0 | MIT | сборка |
| cookie | 1.1.1 | MIT | приложение |
| cssesc | 3.0.0 | MIT | сборка |
| csstype | 3.2.3 | MIT | приложение |
| d3-array | 3.2.4 | ISC | приложение |
| d3-color | 3.1.0 | ISC | приложение |
| d3-ease | 3.0.1 | BSD-3-Clause | приложение |
| d3-format | 3.1.2 | ISC | приложение |
| d3-interpolate | 3.0.1 | ISC | приложение |
| d3-path | 3.1.0 | ISC | приложение |
| d3-scale | 4.0.2 | ISC | приложение |
| d3-shape | 3.2.0 | ISC | приложение |
| d3-time | 3.1.0 | ISC | приложение |
| d3-time-format | 4.1.0 | ISC | приложение |
| d3-timer | 3.0.1 | ISC | приложение |
| dayjs | 1.11.23 | MIT | приложение |
| debug | 4.4.3 | MIT | сборка |
| decimal.js-light | 2.5.1 | MIT | приложение |
| detect-node-es | 1.1.0 | MIT | приложение |
| dom-helpers | 5.2.1 | MIT | приложение |
| electron-to-chromium | 1.5.463 | ISC | сборка |
| esbuild | 0.25.12 | MIT | сборка |
| escalade | 3.2.0 | MIT | сборка |
| eventemitter3 | 4.0.7 | MIT | приложение |
| fast-equals | 5.4.5 | MIT | приложение |
| fdir | 6.5.0 | MIT | сборка |
| fsevents | 2.3.3 | MIT | сборка |
| gensync | 1.0.0-beta.2 | MIT | сборка |
| get-nonce | 1.0.1 | MIT | приложение |
| internmap | 2.0.3 | ISC | приложение |
| js-tokens | 4.0.0 | MIT | приложение |
| jsesc | 3.1.0 | MIT | сборка |
| json5 | 2.2.3 | MIT | сборка |
| lodash | 4.18.1 | MIT | приложение |
| loose-envify | 1.4.0 | MIT | приложение |
| lru-cache | 5.1.1 | ISC | сборка |
| ms | 2.1.3 | MIT | сборка |
| nanoid | 3.3.20 | MIT | сборка |
| node-releases | 2.0.59 | MIT | сборка |
| object-assign | 4.1.1 | MIT | приложение |
| picocolors | 1.1.1 | ISC | сборка |
| picomatch | 4.0.7 | MIT | сборка |
| postcss | 8.5.31 | MIT | сборка |
| postcss-js | 4.1.0 | MIT | сборка |
| postcss-mixins | 12.1.2 | MIT | сборка |
| postcss-nested | 7.0.2 | MIT | сборка |
| postcss-preset-mantine | 1.18.0 | MIT | сборка |
| postcss-selector-parser | 7.1.7 | MIT | сборка |
| postcss-simple-vars | 7.0.1 | MIT | сборка |
| prop-types | 15.8.1 | MIT | приложение |
| react | 18.3.1 | MIT | приложение |
| react-dom | 18.3.1 | MIT | приложение |
| react-dropzone-esm | 15.2.0 | MIT | приложение |
| react-is | 16.13.1 | MIT | приложение |
| react-number-format | 5.4.5 | MIT | приложение |
| react-refresh | 0.17.0 | MIT | сборка |
| react-remove-scroll | 2.7.2 | MIT | приложение |
| react-remove-scroll-bar | 2.3.8 | MIT | приложение |
| react-router | 7.18.4 | MIT | приложение |
| react-router-dom | 7.18.4 | MIT | приложение |
| react-smooth | 4.0.4 | MIT | приложение |
| react-style-singleton | 2.2.3 | MIT | приложение |
| react-textarea-autosize | 8.5.9 | MIT | приложение |
| react-transition-group | 4.4.5 | BSD-3-Clause | приложение |
| recharts | 2.15.4 | MIT | приложение |
| recharts-scale | 0.4.5 | MIT | приложение |
| react-is | 18.3.1 | MIT | приложение |
| rollup | 4.64.12 | MIT | сборка |
| scheduler | 0.23.2 | MIT | приложение |
| semver | 6.3.1 | ISC | сборка |
| set-cookie-parser | 2.7.2 | MIT | приложение |
| source-map-js | 1.2.2 | BSD-3-Clause | сборка |
| sugarss | 5.0.2 | MIT | сборка |
| tabbable | 6.5.0 | MIT | приложение |
| tiny-invariant | 1.3.3 | MIT | приложение |
| tinyglobby | 0.2.17 | MIT | сборка |
| tslib | 2.8.1 | 0BSD | приложение |
| type-fest | 4.41.0 | (MIT OR CC0-1.0) | приложение |
| typescript | 5.9.3 | Apache-2.0 | сборка |
| update-browserslist-db | 1.3.4 | MIT | сборка |
| use-callback-ref | 1.3.3 | MIT | приложение |
| use-composed-ref | 1.4.0 | MIT | приложение |
| use-isomorphic-layout-effect | 1.2.1 | MIT | приложение |
| use-latest | 1.3.0 | MIT | приложение |
| use-sidecar | 1.1.3 | MIT | приложение |
| util-deprecate | 1.0.2 | MIT | сборка |
| victory-vendor | 36.9.2 | MIT AND ISC | приложение |
| vite | 6.4.5 | MIT | сборка |
| yallist | 3.1.1 | ISC | сборка |
