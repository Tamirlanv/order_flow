import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import new_token, password_hasher, token_hash, verify_password
from app.integrations.email import Mailer
from app.modules.identity.models import EmailVerification, Session, User

INVALID_LINK = "Ссылка недействительна или истекла"


class IdentityService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Callable[[], datetime],
        mailer: Mailer,
    ) -> None:
        self.sessions = sessions
        self.clock = clock
        self.mailer = mailer

    async def register(self, email: str, password: str) -> None:
        encoded = await asyncio.to_thread(password_hasher.hash, password)
        async with self.sessions.begin() as db:
            result = await db.execute(
                insert(User)
                .values(id=uuid4(), email=email, password_hash=encoded, created_at=self.clock())
                .on_conflict_do_nothing(index_elements=[User.email])
                .returning(User.id)
            )
            user_id = result.scalar_one_or_none()
        if user_id is not None:
            await self.request_verification(email)

    async def request_verification(self, email: str) -> None:
        raw = new_token()
        now = self.clock()
        verification_id = uuid4()
        async with self.sessions.begin() as db:
            user = await db.scalar(select(User).where(User.email == email).with_for_update())
            if user is None or user.email_verified_at is not None:
                return
            await db.execute(
                update(EmailVerification)
                .where(EmailVerification.user_id == user.id, EmailVerification.used_at.is_(None))
                .values(used_at=now)
            )
            db.add(
                EmailVerification(
                    id=verification_id,
                    user_id=user.id,
                    token_hash=token_hash(raw),
                    expires_at=now + timedelta(hours=24),
                    delivery_status="pending",
                )
            )
        sent = await self.mailer.send_verification(email, raw)
        async with self.sessions.begin() as db:
            await db.execute(
                update(EmailVerification)
                .where(EmailVerification.id == verification_id)
                .values(delivery_status="sent" if sent else "failed")
            )

    async def confirm_verification(self, raw: str) -> None:
        async with self.sessions.begin() as db:
            subject = await db.scalar(
                select(EmailVerification.user_id).where(
                    EmailVerification.token_hash == token_hash(raw)
                )
            )
            if subject is None:
                raise HTTPException(400, INVALID_LINK)
            user = await db.scalar(select(User).where(User.id == subject).with_for_update())
            verification = await db.scalar(
                select(EmailVerification)
                .where(EmailVerification.token_hash == token_hash(raw))
                .with_for_update()
            )
            now = self.clock()
            if (
                user is None
                or verification is None
                or verification.used_at is not None
                or verification.expires_at <= now
            ):
                raise HTTPException(400, INVALID_LINK)
            user.email_verified_at = now
            await db.execute(
                update(EmailVerification)
                .where(EmailVerification.user_id == subject, EmailVerification.used_at.is_(None))
                .values(used_at=now)
            )

    async def login(self, email: str, password: str, previous: str | None) -> tuple[User, str]:
        async with self.sessions() as db:
            candidate = await db.scalar(select(User).where(User.email == email))
            encoded = candidate.password_hash if candidate else None
        valid = await asyncio.to_thread(verify_password, password, encoded)
        if not valid or candidate is None:
            raise HTTPException(401, "Неверный email или пароль")
        now = self.clock()
        raw = new_token()
        async with self.sessions.begin() as db:
            user = await db.scalar(select(User).where(User.id == candidate.id).with_for_update())
            if user is None or user.password_hash != encoded:
                raise HTTPException(401, "Неверный email или пароль")
            if user.email_verified_at is None:
                raise HTTPException(403, "Подтвердите email перед входом")
            if previous:
                await db.execute(
                    update(Session)
                    .where(Session.token_hash == token_hash(previous), Session.revoked_at.is_(None))
                    .values(revoked_at=now)
                )
            db.add(
                Session(
                    user_id=user.id, token_hash=token_hash(raw), expires_at=now + timedelta(days=7)
                )
            )
        return user, raw

    async def current_user(self, raw: str | None) -> User:
        if raw:
            async with self.sessions() as db:
                user = await db.scalar(
                    select(User)
                    .join(Session)
                    .where(
                        Session.token_hash == token_hash(raw),
                        Session.revoked_at.is_(None),
                        Session.expires_at > self.clock(),
                        User.email_verified_at.is_not(None),
                    )
                )
                if user:
                    return user
        raise HTTPException(401, "Войдите в аккаунт")

    async def logout(self, raw: str | None) -> None:
        if raw:
            async with self.sessions.begin() as db:
                await db.execute(
                    update(Session)
                    .where(Session.token_hash == token_hash(raw), Session.revoked_at.is_(None))
                    .values(revoked_at=self.clock())
                )
