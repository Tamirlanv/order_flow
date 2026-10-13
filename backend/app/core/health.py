import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol

from kombu import Connection
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings

HealthState = Literal["ok", "unavailable"]


class HealthChecker(Protocol):
    async def check(self) -> dict[str, HealthState]: ...


async def run_checks(
    probes: dict[str, Callable[[], Awaitable[None]]],
    budget: float,
) -> dict[str, HealthState]:
    async def run(probe: Callable[[], Awaitable[None]]) -> HealthState:
        try:
            await asyncio.wait_for(probe(), timeout=budget)
            return "ok"
        except Exception:
            # Never expose connection strings, credentials or provider error details.
            return "unavailable"

    results = await asyncio.gather(*(run(probe) for probe in probes.values()))
    return dict(zip(probes, results, strict=True))


class InfrastructureHealth:
    def __init__(self, settings: Settings, engine: AsyncEngine) -> None:
        self.settings = settings
        self.engine = engine
        self.redis = Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    async def postgres(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def cache(self) -> None:
        await self.redis.ping()

    async def broker(self) -> None:
        def connect() -> None:
            with Connection(self.settings.broker_url, connect_timeout=2) as connection:
                connection.connect()

        await asyncio.to_thread(connect)

    async def check(self) -> dict[str, HealthState]:
        return await run_checks(
            {"postgres": self.postgres, "redis": self.cache, "rabbitmq": self.broker},
            self.settings.health_timeout_seconds,
        )

    async def close(self) -> None:
        await self.redis.aclose()
