# Частые команды. Всё то же можно выполнить напрямую — см. README.
.PHONY: up down reset logs ps e2e newman test lint docs notices testdata scorecard ai

up:            ## собрать и запустить стенд: http://localhost:8080
	docker compose up -d --build
	@echo "Готово: http://localhost:8080 (пароль тестовых учёток — Demo-2026)"

down:          ## остановить стенд (данные сохраняются)
	docker compose down

reset:         ## остановить и удалить данные (следующий up создаст всё заново)
	docker compose down -v

logs:          ## журналы API и воркеров
	docker compose logs -f api worker

ps:
	docker compose ps -a

e2e:           ## сквозные сценарии S1–S8 против запущенного стенда
	python3 tests/e2e/run_scenarios.py --base http://localhost:8080 --mocks http://localhost:8081

newman:        ## коллекция Postman (сценарии S1 и S2) против запущенного стенда
	curl -fsS -X POST http://localhost:8081/admin/reset > /dev/null
	npx -y newman@6 run docs/05-api/postman_collection.json --working-dir . \
	  --folder "Сценарий S1: экспресс-кредит от заявки до выдачи" --folder "Сценарий S2: бухгалтер → директор → аналитик → комитет"

test:          ## модульные и интеграционные тесты бэкенда (интеграционным нужна PostgreSQL: DATABASE_URL_TEST)
	cd backend && python -m pytest -p no:logging

lint:
	cd backend && ruff check --config pyproject.toml app tests scripts ../mocks ../tests/e2e
	cd frontend && npm run typecheck

docs:          ## обновить сгенерированную документацию (OpenAPI, Postman, диаграммы)
	cd backend && python scripts/gen_docs.py

notices:       ## пересобрать THIRD_PARTY_NOTICES.md
	python scripts/third_party_notices.py

testdata:      ## перегенерировать синтетические документы и выписки (нужен reportlab)
	python scripts/make_test_data.py

scorecard:     ## пересобрать и провалидировать скоринговую карту
	python3 ml/build_scorecard.py

ai:            ## запустить стенд с локальной LLM (Ollama + Qwen2.5)
	LLM_PROVIDER=openai_compatible docker compose --profile ai up -d --build
