from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import quote

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: SecretStr = SecretStr("change-me-local-app-secret")
    outbox_encryption_key: SecretStr = SecretStr("change-me-local-outbox-key")
    idempotency_encryption_key: SecretStr = SecretStr("change-me-local-idempotency-key")
    public_app_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "orderflow"
    postgres_user: str = "orderflow"
    postgres_password: SecretStr = SecretStr("change-me-local-db")
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    rabbitmq_host: str = "127.0.0.1"
    rabbitmq_port: int = Field(default=5672, ge=1, le=65535)
    rabbitmq_user: str = "orderflow"
    rabbitmq_password: SecretStr = SecretStr("change-me-local-broker")
    smtp_host: str = "127.0.0.1"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_from: str = "noreply@orderflow.local"
    storage_root: Path = Path("./data/files")
    health_timeout_seconds: float = Field(default=3.0, gt=0, le=10)

    @model_validator(mode="after")
    def validate_production(self) -> Self:
        if self.app_env != "production":
            return self
        for name in (
            "app_secret_key",
            "outbox_encryption_key",
            "idempotency_encryption_key",
            "postgres_password",
            "rabbitmq_password",
        ):
            value = getattr(self, name).get_secret_value()
            if len(value) < 32 or value.startswith("change-me"):
                raise ValueError(f"Production requires a non-default {name} of 32+ characters")
        if self.public_app_url.scheme != "https":
            raise ValueError("Production requires HTTPS PUBLIC_APP_URL")
        return self

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def broker_url(self) -> str:
        user = quote(self.rabbitmq_user, safe="")
        password = quote(self.rabbitmq_password.get_secret_value(), safe="")
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}//"


@lru_cache
def get_settings() -> Settings:
    return Settings()
