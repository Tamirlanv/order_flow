"""Opt-in tests against local Compose; never clear the application database."""

import os
import smtplib
import subprocess
import sys
import time
from email.message import EmailMessage
from uuid import uuid4

import httpx
import psycopg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from redis import Redis

from app.core.config import Settings
from app.tasks.celery_app import celery_app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1", reason="Requires explicit RUN_INTEGRATION=1 and Compose"
)


def test_live_dependencies_and_nginx() -> None:
    with httpx.Client(timeout=10) as client:
        ready = client.get(f"{os.environ['INTEGRATION_API_URL']}/health/ready")
        assert ready.status_code == 200
        assert ready.json()["checks"] == dict.fromkeys(["postgres", "redis", "rabbitmq"], "ok")
        web = os.environ["INTEGRATION_WEB_URL"]
        assert "OrderFlow" in client.get(web).text
        assert client.get(f"{web}/api/v1/system").json()["name"] == "OrderFlow"


def test_postgres_migration_roundtrip() -> None:
    settings = Settings()
    database = f"orderflow_test_{uuid4().hex}"
    params = dict(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        connect_timeout=5,
    )
    with psycopg.connect(dbname="postgres", autocommit=True, **params) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            env = {**os.environ, "POSTGRES_DB": database}
            head = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            for revision in ["head", "base", "head"]:
                direction = "downgrade" if revision == "base" else "upgrade"
                subprocess.run(
                    [sys.executable, "-m", "alembic", direction, revision],
                    env=env,
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                with psycopg.connect(dbname=database, **params) as connection:
                    rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
                    assert rows == ([] if revision == "base" else [(head,)])
        finally:
            # Only the UUID-named database created by this test is removed.
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def test_redis_roundtrip() -> None:
    key = f"orderflow:test:{uuid4().hex}"
    with Redis.from_url(Settings().redis_url.get_secret_value(), socket_timeout=3) as cache:
        try:
            cache.set(key, b"roundtrip", ex=30)
            assert cache.get(key) == b"roundtrip"
            assert 0 < cache.ttl(key) <= 30
        finally:
            cache.delete(key)


def test_worker_reachable_through_rabbitmq() -> None:
    for _ in range(10):
        replies = celery_app.control.ping(timeout=2)
        if replies:
            assert all(reply == {"ok": "pong"} for node in replies for reply in node.values())
            return
        time.sleep(1)
    pytest.fail("No Celery worker replied through RabbitMQ")


def test_smtp_captured_in_mailpit() -> None:
    settings = Settings()
    marker = f"orderflow-test-{uuid4().hex}"
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = f"{marker}@example.test"
    message["Subject"] = marker
    message.set_content("Local infrastructure verification; no customer data.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
        smtp.send_message(message)
    with httpx.Client(base_url=os.environ["MAILPIT_API_URL"], timeout=5) as client:
        for _ in range(10):
            response = client.get("/api/v1/search", params={"query": f"subject:{marker}"})
            response.raise_for_status()
            messages = response.json()["messages"]
            if messages:
                assert messages[0]["Subject"] == marker
                return
            time.sleep(0.2)
    pytest.fail("SMTP message did not arrive in Mailpit")
