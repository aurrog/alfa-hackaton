"""Интеграционные тесты: настоящая PostgreSQL (DATABASE_URL_TEST), API через TestClient,
симулятор внешних систем в том же процессе, конвейер выполняется синхронно (drain)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

URL = os.environ.get("DATABASE_URL_TEST", "postgresql+psycopg://credit:credit@localhost:5432/credit_test")
BACKEND = Path(__file__).resolve().parents[2]
PASSWORD = "Demo-2026"


@pytest.fixture(scope="session")
def stand():
    try:
        engine = create_engine(URL)
        with engine.connect():
            pass
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL недоступна ({type(e).__name__}) — задайте DATABASE_URL_TEST")
    from alembic.config import Config
    from starlette.testclient import TestClient

    from alembic import command
    from app import db
    from app.config import get_settings
    from app.integrations import client as ic

    s = get_settings()
    s.database_url = URL
    s.pipeline_step_delay_sec = 0
    s.demo_mode = True
    db.reset_engine(URL)
    with engine.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")

    from simulator.main import app as mocks_app
    from simulator.main import reset as mocks_reset

    mocks_reset()
    mocks = TestClient(mocks_app, base_url="http://mocks", headers={"X-Mock-Latency": "0"})
    ic.set_http_client(mocks)
    ic.reset_breakers()

    from app.seed.run import seed_reference, seed_users

    with db.session_factory()() as session:
        seed_reference(session)
        seed_users(session)
        session.commit()
    yield {"mocks": mocks, "factory": db.session_factory()}
    ic.set_http_client(None)
    engine.dispose()


@pytest.fixture(scope="session")
def app_client(stand):

    from app.main import app
    return app


@pytest.fixture
def login(app_client):
    from fastapi.testclient import TestClient

    def _login(email: str) -> TestClient:
        c = TestClient(app_client)
        r = c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        c.company = (c.get("/api/v1/auth/me").json()["companies"] or [None])[0]
        return c
    return _login


@pytest.fixture
def drain(stand):
    from app.worker.runner import drain as _drain

    def _run() -> int:
        return _drain(stand["factory"], "test")
    return _run


@pytest.fixture
def mocks(stand):
    from simulator.main import STATE
    yield stand["mocks"]
    STATE["faults"].clear()
