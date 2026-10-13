import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings


def test_passwords_are_escaped_in_connection_urls() -> None:
    config = Settings(
        _env_file=None,
        postgres_password=SecretStr("a@b:/%"),
        rabbitmq_password=SecretStr("a@b:/%"),
    )
    assert config.database_url.password == "a@b:/%"
    assert "a%40b%3A%2F%25" in config.broker_url
    assert "a@b:/%" not in repr(config)


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(_env_file=None, app_env="production")


def test_invalid_port_and_timeout_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, postgres_port=0, health_timeout_seconds=0)


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "5544")
    monkeypatch.setenv("POSTGRES_HOST", "test-db")
    config = Settings(_env_file=None)
    assert config.database_url.host == "test-db"
    assert config.database_url.port == 5544


def test_production_validation_does_not_print_secret_input() -> None:
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            app_env="production",
            postgres_password=SecretStr("private-credential-must-not-be-printed"),
        )
    assert "private-credential-must-not-be-printed" not in str(error.value)


def test_production_accepts_configured_secrets_and_requires_https() -> None:
    secrets = {
        key: SecretStr("a-unique-test-only-secret-value-of-40-chars")
        for key in (
            "app_secret_key",
            "outbox_encryption_key",
            "idempotency_encryption_key",
            "postgres_password",
            "rabbitmq_password",
        )
    }
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(_env_file=None, app_env="production", **secrets)
    config = Settings(
        _env_file=None, app_env="production", public_app_url="https://orderflow.example", **secrets
    )
    assert config.public_app_url.scheme == "https"
