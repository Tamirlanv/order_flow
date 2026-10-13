from collections.abc import Awaitable
from typing import cast

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.security import keyed_hash

_INCREMENT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


class RateLimiter:
    def __init__(self, redis: Redis, secret: str) -> None:
        self.redis = redis
        self.secret = secret

    async def allow(self, scope: str, subject: str, limit: int, seconds: int) -> bool:
        key = f"orderflow:limit:{scope}:{keyed_hash(self.secret, subject)}"
        try:
            count = await cast(Awaitable[int], self.redis.eval(_INCREMENT, 1, key, str(seconds)))
        except RedisError:
            raise HTTPException(503, "Сервис временно недоступен") from None
        return count <= limit

    async def require(self, scope: str, subject: str, limit: int, seconds: int) -> None:
        if not await self.allow(scope, subject, limit, seconds):
            raise HTTPException(
                429,
                "Слишком много запросов. Попробуйте позже",
                headers={"Retry-After": str(seconds)},
            )
