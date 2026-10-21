from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.database_url, pool_pre_ping=True, pool_size=s.db_pool_size, max_overflow=10,
                                future=True)
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _factory
    if _factory is None:
        _factory = sessionmaker(bind=engine(), expire_on_commit=False, autoflush=False)
    return _factory


def reset_engine(url: str | None = None) -> None:
    """Для тестов: пересоздать движок на другой URL."""
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
    if url:
        get_settings().database_url = url


def get_session() -> Iterator[Session]:
    """FastAPI-зависимость: сессия на запрос.

    Изменяющие эндпоинты фиксируют транзакцию явно (`db.commit()`) до формирования
    ответа — клиент получает ответ только после того, как данные сохранены.
    Незафиксированные изменения откатываются при закрытии сессии.
    """
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
