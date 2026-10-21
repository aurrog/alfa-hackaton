import os
import sys
from pathlib import Path

# симулятор внешних систем подключается в интеграционных тестах в том же процессе
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mocks"))
os.environ.setdefault("PIPELINE_STEP_DELAY_SEC", "0")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("STORAGE_DIR", str(Path(__file__).resolve().parent / ".uploads"))
