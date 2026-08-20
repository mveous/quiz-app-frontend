import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger("mveousquiz")


class EmailService:
    """Sends transactional emails over SMTP.

    If SMTP_HOST is unset (local dev without credentials yet), emails are
    logged instead of sent so the reset/verification flow stays usable.
    """

    async def send_password_reset_email(self, to_email: str, full_name: str, reset_url: str) -> None:
        subject = "Reset your MveousQuiz password"
        html_body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto">
  <h2 style="color:#111">Reset your password</h2>
  <p>Hi {full_name},</p>
  <p>We received a request to reset your MveousQuiz password. This link expires in
  {settings.password_reset_token_expire_minutes} minutes.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}" style="background:#111;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none">
      Reset password
    </a>
  </p>
  <p>If you didn't request this, you can safely ignore this email.</p>
</div>"""
        text_body = (
            f"Hi {full_name},\n\n"
            "We received a request to reset your MveousQuiz password. "
            f"This link expires in {settings.password_reset_token_expire_minutes} minutes.\n\n"
            f"{reset_url}\n\n"
            "If you didn't request this, you can safely ignore this email."
        )
        await self._send(to_email, subject, text_body, html_body)

    async def _send(self, to_email: str, subject: str, text_body: str, html_body: str) -> None:
        if not settings.smtp_host:
            logger.info("SMTP not configured — logging email instead of sending.\nTo: %s\nSubject: %s\n%s",
                        to_email, subject, text_body)
            return

        message = EmailMessage()
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_use_tls,
        )


email_service = EmailService()
