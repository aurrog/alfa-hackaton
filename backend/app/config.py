"""Конфигурация через переменные окружения (12-factor). Полный список — в README."""

from __future__ import annotations

import socket
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field("development", description="development | test | production")
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://credit:credit@localhost:5432/credit"
    db_pool_size: int = 10

    jwt_secret: str = "dev-only-secret-change-me-before-deploy"
    jwt_ttl_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    integrations_base_url: str = "http://localhost:8081"
    integration_timeout_sec: float = 3.0
    integration_retries: int = 2
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_sec: float = 30.0

    storage_dir: str = "./data/uploads"
    max_upload_mb: int = 10

    pipeline_step_delay_sec: float = 1.2
    worker_poll_interval_sec: float = 0.5
    worker_id: str = Field(default_factory=socket.gethostname)
    worker_metrics_port: int = 9100
    job_max_attempts: int = 4
    job_lease_sec: int = 300

    demo_mode: bool = True
    seed_history: int = 60

    llm_provider: str = "none"  # none | openai_compatible
    llm_base_url: str = "http://ollama:11434/v1"
    llm_model: str = "qwen2.5:1.5b-instruct"
    llm_timeout_sec: float = 40.0

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def check_production_safety(self) -> None:
        if self.app_env == "production" and self.jwt_secret.startswith("dev-only"):
            raise RuntimeError("JWT_SECRET must be set in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
