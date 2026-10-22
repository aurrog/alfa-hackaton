"""Точка входа воркера: `python -m app.worker`."""

from __future__ import annotations

import contextlib
import signal
import threading

from prometheus_client import start_http_server

from app.config import get_settings
from app.db import session_factory
from app.logging_setup import setup_logging
from app.worker.runner import loop


def main() -> None:
    s = get_settings()
    setup_logging(s.log_level)
    stop = threading.Event()

    def _graceful(*_):  # SIGTERM от Docker: доделать текущую задачу и выйти
        stop.set()

    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)
    with contextlib.suppress(OSError):
        start_http_server(s.worker_metrics_port, addr=s.worker_metrics_host)
    loop(session_factory(), stop.is_set)


if __name__ == "__main__":
    main()
