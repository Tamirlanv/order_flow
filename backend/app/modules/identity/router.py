import hmac
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.core.security import csrf_token, new_token
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/api/v1/auth", tags=["Accounts"])
SESSION_COOKIE = "orderflow_session"
CSRF_COOKIE = "orderflow_csrf_seed"
NEUTRAL = "Если адрес подходит для регистрации, мы отправили инструкции"


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class Credentials(EmailInput):
    password: str = Field(min_length=12, max_length=128)


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=1, max_length=128)


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class LoginView(BaseModel):
    user: UserView
    csrf_token: str


def config(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def identity(request: Request) -> IdentityService:
    return cast(IdentityService, request.app.state.identity)


def limiter(request: Request) -> RateLimiter:
    return cast(RateLimiter, request.app.state.limiter)


def ip(request: Request) -> str:
    # Proxy headers are not trusted here; no client-supplied X-Forwarded-For bypass.
    return request.client.host if request.client else "unknown"


def binding(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE) or request.cookies.get(CSRF_COOKIE, "")


def set_cookie(response: Response, settings: Settings, name: str, value: str, seconds: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=seconds,
        httponly=True,
        samesite="lax",
        secure=settings.public_app_url.scheme == "https",
        path="/",
    )


def require_csrf(request: Request) -> None:
    settings = config(request)
    origin = str(settings.public_app_url).rstrip("/")
    seed = binding(request)
    expected = csrf_token(settings.app_secret_key.get_secret_value(), seed)
    actual = request.headers.get("x-csrf-token", "")
    if (
        request.headers.get("origin") != origin
        or not seed
        or not hmac.compare_digest(expected.encode(), actual.encode())
    ):
        raise HTTPException(403, "Запрос отклонён. Обновите страницу")


Service = Annotated[IdentityService, Depends(identity)]
CSRF = Depends(require_csrf)


@router.get("/csrf")
async def issue_csrf(request: Request, response: Response) -> dict[str, str]:
    seed = binding(request)
    if not seed:
        seed = new_token()
        set_cookie(response, config(request), CSRF_COOKIE, seed, 3600)
    return {"csrf_token": csrf_token(config(request).app_secret_key.get_secret_value(), seed)}


@router.post("/register", status_code=202, dependencies=[CSRF])
async def register(body: Credentials, request: Request, service: Service) -> dict[str, str]:
    limits = limiter(request)
    await limits.require("email-ip", ip(request), 10, 3600)
    if await limits.allow("verification-email", str(body.email), 3, 3600):
        await service.register(str(body.email), body.password)
    return {"message": NEUTRAL}


@router.post("/verification/request", status_code=202, dependencies=[CSRF])
async def resend(body: EmailInput, request: Request, service: Service) -> dict[str, str]:
    limits = limiter(request)
    await limits.require("email-ip", ip(request), 10, 3600)
    if await limits.allow("verification-email", str(body.email), 3, 3600):
        await service.request_verification(str(body.email))
    return {"message": NEUTRAL}


@router.post("/verification/confirm", status_code=204, dependencies=[CSRF])
async def confirm(body: TokenInput, request: Request, service: Service) -> None:
    await limiter(request).require("verification-confirm", ip(request), 20, 60)
    await service.confirm_verification(body.token)


@router.post("/login", dependencies=[CSRF])
async def login(
    body: Credentials, request: Request, response: Response, service: Service
) -> LoginView:
    limits = limiter(request)
    await limits.require("login-ip", ip(request), 20, 900)
    await limits.require("login-email", str(body.email), 10, 900)
    user, raw = await service.login(
        str(body.email), body.password, request.cookies.get(SESSION_COOKIE)
    )
    settings = config(request)
    set_cookie(response, settings, SESSION_COOKIE, raw, 7 * 86400)
    response.delete_cookie(CSRF_COOKIE, path="/")
    return LoginView(
        user=UserView.model_validate(user),
        csrf_token=csrf_token(settings.app_secret_key.get_secret_value(), raw),
    )


@router.get("/me")
async def me(request: Request, service: Service) -> UserView:
    return UserView.model_validate(await service.current_user(request.cookies.get(SESSION_COOKIE)))


@router.post("/logout", status_code=204, dependencies=[CSRF])
async def logout(request: Request, response: Response, service: Service) -> None:
    await service.logout(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
