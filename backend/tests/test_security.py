from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import AnyHttpUrl
from redis.exceptions import ConnectionError

from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.core.security import csrf_token, new_token, password_hasher, token_hash, verify_password
from app.integrations.email import SMTPMailer
from app.main import create_app


def test_password_hash_verifies_unicode_and_spaces() -> None:
    password = "длинный пароль с пробелами 123"
    encoded = password_hasher.hash(password)
    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("неверный пароль", encoded)
    assert not verify_password(password, None)
    assert not verify_password(password, "damaged hash")


def test_tokens_and_csrf_are_bound_to_secret_and_session() -> None:
    first, second = new_token(), new_token()
    assert len(first) >= 43 and first != second
    assert len(token_hash(first)) == 64 and first not in token_hash(first)
    assert csrf_token("secret", first) != csrf_token("secret", second)
    assert csrf_token("secret", first) != csrf_token("other", first)


async def test_rate_limit_fails_closed_without_redis() -> None:
    cache = AsyncMock()
    cache.eval.side_effect = ConnectionError("secret connection details")
    with pytest.raises(HTTPException) as error:
        await RateLimiter(cache, "test-key").allow("login", "private@email.example", 1, 60)
    assert error.value.status_code == 503
    assert "secret" not in error.value.detail


async def test_smtp_failure_has_no_secrets_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    with patch("app.integrations.email.smtplib.SMTP", side_effect=OSError("secret details")):
        assert not await SMTPMailer(Settings(_env_file=None)).send_verification(
            "private@example.com", "raw-private-token"
        )
    assert "email_verification_delivery_failed" in caplog.text
    assert "secret details" not in caplog.text
    assert "private" not in caplog.text


async def test_https_csrf_cookie_has_safe_flags() -> None:
    app = create_app(Settings(_env_file=None, public_app_url=AnyHttpUrl("https://test")))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client,
    ):
        result = await client.get("/api/v1/auth/csrf")
    cookie = result.headers["set-cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Domain=" not in cookie
    assert result.headers["cache-control"] == "no-store"
