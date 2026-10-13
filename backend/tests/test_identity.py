import asyncio
import os
import re
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import psycopg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from psycopg import sql
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.security import token_hash
from app.integrations.email import SMTPMailer
from app.main import create_app
from app.modules.identity.models import EmailVerification, Session, User

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1", reason="Requires PostgreSQL/Redis"
)
PASSWORD = "мой длинный пароль 123"
EMAIL = "owner@example.com"


@pytest.fixture
def identity_settings() -> Iterator[Settings]:
    settings = Settings()
    database = f"orderflow_test_{uuid4().hex}"
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        dbname="postgres",
        autocommit=True,
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                env={**os.environ, "POSTGRES_DB": database},
                check=True,
                capture_output=True,
                timeout=30,
            )
            yield settings.model_copy(
                update={
                    "postgres_db": database,
                    "app_env": "test",
                    "app_secret_key": SecretStr(uuid4().hex + uuid4().hex),
                }
            )
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


@dataclass
class Mailbox:
    sent: list[tuple[str, str]] = field(default_factory=list)
    succeeds: bool = True

    async def send_verification(self, email: str, token: str) -> bool:
        self.sent.append((email, token))
        return self.succeeds


@dataclass
class Environment:
    app: FastAPI
    client: AsyncClient
    mailbox: Mailbox
    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    async def register(self) -> str:
        response = await self.client.post(
            "/api/v1/auth/register",
            json={
                "email": EMAIL,
                "password": PASSWORD,
            },
        )
        assert response.status_code == 202, response.text
        return self.mailbox.sent[-1][1]

    async def verified(self) -> None:
        raw = await self.register()
        assert (
            await self.client.post("/api/v1/auth/verification/confirm", json={"token": raw})
        ).status_code == 204

    async def login(self) -> httpx.Response:
        response = await self.client.post(
            "/api/v1/auth/login",
            json={
                "email": EMAIL,
                "password": PASSWORD,
            },
        )
        if response.status_code == 200:
            self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return response


@pytest_asyncio.fixture
async def auth(identity_settings: Settings) -> AsyncIterator[Environment]:
    app = create_app(identity_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": str(identity_settings.public_app_url).rstrip("/")},
        ) as client,
    ):
        environment = Environment(app, client, Mailbox())
        app.state.identity.clock = lambda: environment.now
        app.state.identity.mailer = environment.mailbox
        response = await client.get("/api/v1/auth/csrf")
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield environment


async def test_registration_confirmation_login_logout(auth: Environment) -> None:
    raw = await auth.register()
    assert (await auth.login()).status_code == 403
    result = await auth.client.post("/api/v1/auth/verification/confirm", json={"token": raw})
    assert result.status_code == 204
    result = await auth.login()
    assert result.status_code == 200
    assert (
        "HttpOnly" in result.headers["set-cookie"]
        and "SameSite=lax" in result.headers["set-cookie"]
    )
    session = auth.client.cookies["orderflow_session"]
    async with auth.app.state.identity.sessions() as db:
        assert (await db.scalar(select(Session.token_hash))) == token_hash(session)
        assert (await db.scalar(select(EmailVerification.token_hash))) == token_hash(raw)
        assert (await db.scalar(select(User.password_hash))).startswith("$argon2id$")
    result = await auth.client.get("/api/v1/auth/me")
    assert result.json()["email"] == EMAIL
    assert result.headers["cache-control"] == "no-store"
    assert (await auth.client.post("/api/v1/auth/logout")).status_code == 204
    auth.client.cookies.set("orderflow_session", session)
    assert (await auth.client.get("/api/v1/auth/me")).status_code == 401


async def test_expired_reused_and_concurrent_verification(auth: Environment) -> None:
    raw = await auth.register()
    auth.now += timedelta(hours=24)
    assert (
        await auth.client.post("/api/v1/auth/verification/confirm", json={"token": raw})
    ).status_code == 400
    await auth.client.post("/api/v1/auth/verification/request", json={"email": EMAIL})
    fresh = auth.mailbox.sent[-1][1]
    responses = await asyncio.gather(
        *[
            auth.client.post("/api/v1/auth/verification/confirm", json={"token": fresh})
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [204, 400]
    assert (
        await auth.client.post("/api/v1/auth/verification/confirm", json={"token": fresh})
    ).status_code == 400


async def test_resend_invalidates_previous_and_recovers_failed_delivery(auth: Environment) -> None:
    auth.mailbox.succeeds = False
    old = await auth.register()
    async with auth.app.state.identity.sessions() as db:
        assert (await db.scalar(select(EmailVerification.delivery_status))) == "failed"
    auth.mailbox.succeeds = True
    assert (
        await auth.client.post("/api/v1/auth/verification/request", json={"email": EMAIL})
    ).status_code == 202
    assert (
        await auth.client.post("/api/v1/auth/verification/confirm", json={"token": old})
    ).status_code == 400
    assert (
        await auth.client.post(
            "/api/v1/auth/verification/confirm", json={"token": auth.mailbox.sent[-1][1]}
        )
    ).status_code == 204


async def test_duplicate_registration_preserves_password_and_unique_user(auth: Environment) -> None:
    await auth.verified()
    results = await asyncio.gather(
        *[
            auth.client.post(
                "/api/v1/auth/register",
                json={
                    "email": " OWNER@EXAMPLE.COM ",
                    "password": "a different long password",
                },
            )
            for _ in range(2)
        ]
    )
    assert all(r.status_code == 202 for r in results)
    async with auth.app.state.identity.sessions() as db:
        assert (await db.scalar(select(func.count()).select_from(User))) == 1
    assert (await auth.login()).status_code == 200


async def test_bad_credentials_and_expired_session(auth: Environment) -> None:
    await auth.verified()
    wrong = await auth.client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "a wrong long password"}
    )
    missing = await auth.client.post(
        "/api/v1/auth/login", json={"email": "absent@example.com", "password": PASSWORD}
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert (await auth.login()).status_code == 200
    auth.now += timedelta(days=7)
    assert (await auth.client.get("/api/v1/auth/me")).status_code == 401


async def test_csrf_origin_session_rotation_and_safe_validation(auth: Environment) -> None:
    body = {"email": EMAIL, "password": PASSWORD}
    assert (
        await auth.client.post("/api/v1/auth/register", json=body, headers={"X-CSRF-Token": ""})
    ).status_code == 403
    assert (
        await auth.client.post(
            "/api/v1/auth/register", json=body, headers={"Origin": "https://evil.example"}
        )
    ).status_code == 403
    bad = await auth.client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": "secret"}
    )
    assert bad.status_code == 422 and "secret" not in bad.text and "input" not in bad.text
    await auth.verified()
    old = auth.client.headers["X-CSRF-Token"]
    assert (await auth.login()).status_code == 200
    assert (
        await auth.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": old})
    ).status_code == 403
    assert (await auth.client.get("/api/v1/auth/me")).status_code == 200


async def test_email_and_ip_limits_are_atomic(auth: Environment) -> None:
    await auth.register()
    for _ in range(4):
        assert (
            await auth.client.post("/api/v1/auth/verification/request", json={"email": EMAIL})
        ).status_code == 202
    assert len(auth.mailbox.sent) == 3
    limits = auth.app.state.limiter
    results = await asyncio.gather(*[limits.allow("atomic", "subject", 3, 60) for _ in range(12)])
    assert sum(results) == 3
    for _ in range(5):
        await auth.client.post(
            "/api/v1/auth/verification/request", json={"email": "absent@example.com"}
        )
    response = await auth.client.post("/api/v1/auth/verification/request", json={"email": EMAIL})
    assert response.status_code == 429 and "retry-after" in response.headers


async def test_verification_delivered_via_real_smtp(auth: Environment) -> None:
    auth.app.state.identity.mailer = SMTPMailer(auth.app.state.settings)
    email = f"owner-{uuid4().hex}@example.com"
    assert (
        await auth.client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    ).status_code == 202
    async with httpx.AsyncClient(base_url=os.environ["MAILPIT_API_URL"], timeout=5) as mail:
        messages = (await mail.get("/api/v1/search", params={"query": f"to:{email}"})).json()[
            "messages"
        ]
        assert len(messages) == 1
        letter = (await mail.get(f"/api/v1/message/{messages[0]['ID']}")).json()
        raw = re.search(r"#verify=([\w-]+)", letter["Text"])[1]
    assert (
        await auth.client.post("/api/v1/auth/verification/confirm", json={"token": raw})
    ).status_code == 204
    response = await auth.client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_concurrent_new_registration_creates_one_account(auth: Environment) -> None:
    results = await asyncio.gather(
        *[
            auth.client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD})
            for _ in range(2)
        ]
    )
    assert all(response.status_code == 202 for response in results)
    assert len(auth.mailbox.sent) == 1
    async with auth.app.state.identity.sessions() as db:
        assert (await db.scalar(select(func.count()).select_from(User))) == 1


async def test_unknown_token_and_email_login_throttling(auth: Environment) -> None:
    response = await auth.client.post(
        "/api/v1/auth/verification/confirm", json={"token": "unknown"}
    )
    assert response.status_code == 400
    for _ in range(10):
        response = await auth.client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert response.status_code == 401
    response = await auth.client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 429
