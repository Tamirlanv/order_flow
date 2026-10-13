from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.core.config import Settings, get_settings
from app.core.database import make_engine
from app.core.health import HealthChecker, HealthState, InfrastructureHealth
from app.core.rate_limit import RateLimiter
from app.integrations.email import SMTPMailer
from app.modules.identity.router import router as identity_router
from app.modules.identity.service import IdentityService


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
        application.state.identity = IdentityService(
            async_sessionmaker(engine, expire_on_commit=False),
            lambda: datetime.now(UTC),
            SMTPMailer(config),
        )
        application.state.limiter = RateLimiter(
            health.redis, config.app_secret_key.get_secret_value()
        )
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
        description="OrderFlow: accounts and infrastructure. Orders API is planned.",
        docs_url=None,
        redoc_url=None,
    )
    application.state.settings = config
    application.include_router(identity_router)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default includes rejected input (including plaintext passwords).
        safe = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": safe})

    @application.middleware("http")
    async def private_auth_responses(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

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
