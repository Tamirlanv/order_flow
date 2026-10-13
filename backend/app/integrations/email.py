import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    async def send_verification(self, email: str, token: str) -> bool: ...


class SMTPMailer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_verification(self, email: str, token: str) -> bool:
        def send() -> bool:
            message = EmailMessage()
            message["From"] = self.settings.smtp_from
            message["To"] = email
            message["Subject"] = "OrderFlow: подтвердите email"
            url = f"{str(self.settings.public_app_url).rstrip('/')}#verify={token}"
            message.set_content(f"Подтвердите email в OrderFlow:\n{url}\nСсылка действует 24 часа.")
            try:
                with smtplib.SMTP(
                    self.settings.smtp_host, self.settings.smtp_port, timeout=5
                ) as smtp:
                    smtp.send_message(message)
                return True
            except (OSError, smtplib.SMTPException):
                logger.warning("email_verification_delivery_failed")
                return False

        return await asyncio.to_thread(send)
