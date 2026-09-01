import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To

from app.core.config import settings
from app.core.email_templates import (
    EmailContent,
    build_coach_invite_email,
    build_email_verification_email,
    build_password_recovery_email,
    build_password_reset_email,
)

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.SENDGRID_API_KEY and settings.SENDGRID_FROM_EMAIL)


def _build_reset_url(reset_token: str) -> str:
    base_url = settings.RESET_PASSWORD_URL.rstrip("/")
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}token={reset_token}"


def send_email(content: EmailContent, to_email: str) -> None:
    from_email = Email(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME)
    message = Mail(
        from_email=from_email,
        to_emails=To(to_email),
        subject=content.subject,
    )
    message.add_content(Content("text/plain", content.plain_text))
    message.add_content(Content("text/html", content.html))

    client = SendGridAPIClient(settings.SENDGRID_API_KEY)
    response = client.send(message)
    logger.info(
        "Email sent to %s via SendGrid (status=%s)",
        to_email,
        response.status_code,
    )


def send_password_reset_email(to_email: str, reset_token: str) -> None:
    if not email_configured():
        logger.warning("SendGrid is not configured; password reset email was not sent")
        return

    reset_url = _build_reset_url(reset_token)
    content = build_password_reset_email(to_email=to_email, reset_url=reset_url)
    send_email(content, to_email)


def send_password_recovery_email(to_email: str, otp_code: str) -> None:
    """Send the 6-digit password recovery code for player forgot-password."""
    if not email_configured():
        logger.warning("SendGrid is not configured; password recovery email was not sent")
        return

    content = build_password_recovery_email(to_email=to_email, otp_code=otp_code)
    send_email(content, to_email)


def send_verification_email(to_email: str, otp_code: str) -> None:
    """Send the 6-digit email verification code after coach registration."""
    if not email_configured():
        logger.warning("SendGrid is not configured; verification email was not sent")
        return

    content = build_email_verification_email(to_email=to_email, otp_code=otp_code)
    send_email(content, to_email)


def send_coach_invite_email(
    *,
    to_email: str,
    organization_name: str,
    invite_url: str,
) -> None:
    """Send a coach invitation email for organization admin invites."""
    if not email_configured():
        logger.warning("SendGrid is not configured; coach invite email was not sent")
        return

    content = build_coach_invite_email(
        to_email=to_email,
        organization_name=organization_name,
        invite_url=invite_url,
    )
    send_email(content, to_email)


def send_subscription_price_change_email(
    *,
    to_email: str,
    plan_name: str,
    old_price: str,
    new_price: str,
    billing_frequency: str,
) -> None:
    if not email_configured():
        logger.warning("SendGrid is not configured; subscription price-change email was not sent")
        return

    from app.core.email_templates import build_subscription_price_change_email

    content = build_subscription_price_change_email(
        plan_name=plan_name,
        old_price=old_price,
        new_price=new_price,
        billing_frequency=billing_frequency,
    )
    send_email(content, to_email)


def send_subscription_plan_archived_email(
    *,
    to_email: str,
    plan_name: str,
    billing_frequency: str,
    period_end: str | None,
    replacement_plan_name: str | None,
) -> None:
    if not email_configured():
        logger.warning("SendGrid is not configured; subscription archive email was not sent")
        return

    from app.core.email_templates import build_subscription_plan_archived_email

    content = build_subscription_plan_archived_email(
        plan_name=plan_name,
        billing_frequency=billing_frequency,
        period_end=period_end,
        replacement_plan_name=replacement_plan_name,
    )
    send_email(content, to_email)
