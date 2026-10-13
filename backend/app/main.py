from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, Request, Response
from pydantic import BaseModel

from app import __version__
from app.core.config import Settings, get_settings
from app.core.database import make_engine
from app.core.health import HealthChecker, HealthState, InfrastructureHealth


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, HealthState]


class SystemResponse(BaseModel):
    name: str = "OrderFlow"
    version: str = __version__
    stage: Literal["foundation"] = "foundation"


def get_health_checker(request: Request) -> HealthChecker:
    return cast(HealthChecker, request.app.state.health)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(config)
        health = InfrastructureHealth(config, engine)
        application.state.health = health
        try:
            yield
        finally:
            try:
                await health.close()
            finally:
                await engine.dispose()

    application = FastAPI(
        title="OrderFlow API",
        version=__version__,
        lifespan=lifespan,
        description="Order management platform. Foundation endpoints; business API is planned.",
    )

    @application.get("/health/live", tags=["Health"], response_model=LivenessResponse)
    @application.get("/api/v1/health/live", include_in_schema=False)
    async def live() -> LivenessResponse:
        return LivenessResponse()

    @application.get(
        "/health/ready",
        tags=["Health"],
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse, "description": "Dependencies unavailable"}},
    )
    @application.get("/api/v1/health/ready", include_in_schema=False)
    async def ready(
        response: Response,
        checker: Annotated[HealthChecker, Depends(get_health_checker)],
    ) -> ReadinessResponse:
        checks = await checker.check()
        healthy = bool(checks) and all(state == "ok" for state in checks.values())
        response.status_code = 200 if healthy else 503
        response.headers["Cache-Control"] = "no-store"
        return ReadinessResponse(status="ok" if healthy else "unavailable", checks=checks)

    @application.get("/api/v1/system", tags=["System"], response_model=SystemResponse)
    async def system() -> SystemResponse:
        return SystemResponse()

    return application


app = create_app()
