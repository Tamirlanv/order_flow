import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.health import HealthState, InfrastructureHealth, run_checks
from app.main import create_app, get_health_checker


async def test_liveness_and_metadata_do_not_require_infrastructure() -> None:
    application = create_app(Settings(_env_file=None))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        assert (await client.get("/health/live")).json() == {"status": "ok"}
        assert (await client.get("/api/v1/health/live")).status_code == 200
        assert (await client.get("/api/v1/system")).json() == {
            "name": "OrderFlow",
            "version": "0.1.0",
            "stage": "foundation",
        }
        assert (await client.get("/openapi.json")).status_code == 200


@pytest.mark.parametrize("state,code", [("ok", 200), ("unavailable", 503)])
async def test_readiness_reports_dependencies(state: HealthState, code: int) -> None:
    application = create_app(Settings(_env_file=None))
    checker = AsyncMock()
    checker.check.return_value = {"postgres": state, "redis": "ok", "rabbitmq": "ok"}
    application.dependency_overrides[get_health_checker] = lambda: checker
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        response = await client.get("/health/ready")
        assert response.status_code == code
        assert response.json()["checks"]["postgres"] == state
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get("/api/v1/health/ready")).status_code == code


async def test_probe_failure_and_timeout_do_not_leak_exceptions() -> None:
    async def failing() -> None:
        raise RuntimeError("password=secret-in-provider-error")

    async def stalled() -> None:
        await asyncio.Event().wait()

    async def successful() -> None:
        return None

    result = await run_checks(
        {"postgres": failing, "redis": stalled, "rabbitmq": successful},
        budget=0.01,
    )
    assert result == {"postgres": "unavailable", "redis": "unavailable", "rabbitmq": "ok"}
    assert "secret" not in str(result)


async def test_lifespan_closes_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    close = AsyncMock()
    dispose = AsyncMock()
    monkeypatch.setattr(InfrastructureHealth, "close", close)
    engine = AsyncMock()
    engine.dispose = dispose
    monkeypatch.setattr("app.main.make_engine", lambda settings: engine)
    application = create_app(Settings(_env_file=None))
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client,
    ):
        assert (await client.get("/health/live")).status_code == 200
    close.assert_awaited_once()
    dispose.assert_awaited_once()
