import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Wrapper around Brevo SMTP for sending transactional emails."""

    @classmethod
    def _is_configured(cls) -> bool:
        """Check if Brevo SMTP is configured."""
        return all(
            [
                settings.BREVO_SMTP_HOST,
                settings.BREVO_SMTP_PORT,
                settings.BREVO_SMTP_USER,
                settings.BREVO_SMTP_PASSWORD,
                settings.BREVO_FROM_EMAIL,
            ]
        )

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Send an email via Brevo SMTP. Returns (success, error_message)."""

        if not cls._is_configured():
            logger.warning("Brevo SMTP not configured; skipping email to %s", to_email)
            return False, "Brevo SMTP not configured"

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.BREVO_FROM_EMAIL
            msg["To"] = to_email

            if reply_to:
                msg["Reply-To"] = reply_to

            # Attach text part
            text_part = MIMEText(text_body, "plain")
            msg.attach(text_part)

            # Attach HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, "html")
                msg.attach(html_part)

            # Send via Brevo SMTP
            with smtplib.SMTP(settings.BREVO_SMTP_HOST, settings.BREVO_SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(settings.BREVO_SMTP_USER, settings.BREVO_SMTP_PASSWORD)
                smtp.send_message(msg)

            logger.info("Email sent to %s via Brevo SMTP", to_email)
            return True, None

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("Brevo SMTP authentication failed: %s", exc)
            return False, f"SMTP authentication failed: {str(exc)}"
        except smtplib.SMTPException as exc:
            logger.error("Brevo SMTP error for %s: %s", to_email, exc)
            return False, f"SMTP error: {str(exc)}"
        except Exception as exc:
            logger.error("Unexpected error sending email to %s: %s", to_email, exc)
            return False, f"Unexpected error: {str(exc)}"


def render_html_from_text(text: str) -> str:
    """Minimal helper to convert plain text body to HTML."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = [line.strip() for line in escaped.splitlines()]
    return "<br/>".join(filter(None, lines))
