"""`python -m app.seed [--history N]` — наполнить базу тестовыми данными (идемпотентно)."""

from __future__ import annotations

import argparse

from app.seed.run import main

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Тестовые данные кредитного кабинета")
    ap.add_argument("--history", type=int, default=None, help="Сколько заявок истории создать (по умолчанию SEED_HISTORY)")
    args = ap.parse_args()
    main(args.history)
