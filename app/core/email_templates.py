from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings


@dataclass(frozen=True)
class EmailContent:
    subject: str
    plain_text: str
    html: str


def _display_app_name() -> str:
    return settings.APP_NAME.replace(" API", "").strip() or settings.APP_NAME


def render_email(
    *,
    title: str,
    body_html: str,
    preview_text: str,
) -> str:
    app_name = _display_app_name()
    year = datetime.now().year

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body
    style="
      margin: 0;
      padding: 0;
      background-color: #f3f4f6;
      font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
      color: #1f2937;
    "
  >
    <span
      style="
        display: none;
        visibility: hidden;
        opacity: 0;
        color: transparent;
        height: 0;
        width: 0;
        overflow: hidden;
      "
    >
      {preview_text}
    </span>

    <table
      role="presentation"
      width="100%"
      cellspacing="0"
      cellpadding="0"
      style="background-color: #f3f4f6; padding: 32px 16px;"
    >
      <tr>
        <td align="center">
          <table
            role="presentation"
            width="100%"
            cellspacing="0"
            cellpadding="0"
            style="
              max-width: 600px;
              background-color: #ffffff;
              border-radius: 12px;
              overflow: hidden;
              box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
            "
          >
            <tr>
              <td style="padding: 32px;">
                {body_html}
              </td>
            </tr>

            <tr>
              <td
                style="
                  background-color: #f8fafc;
                  border-top: 1px solid #e5e7eb;
                  padding: 24px 32px;
                  text-align: center;
                "
              >
                <p
                  style="
                    margin: 0 0 8px;
                    font-size: 13px;
                    line-height: 1.6;
                    color: #6b7280;
                  "
                >
                  This is an automated message from {app_name}. Please do not reply to this email.
                </p>
                <p
                  style="
                    margin: 0;
                    font-size: 12px;
                    line-height: 1.6;
                    color: #9ca3af;
                  "
                >
                  &copy; {year} {app_name}. All rights reserved.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_password_reset_email(*, to_email: str, reset_url: str) -> EmailContent:
    app_name = _display_app_name()
    expire_hours = settings.RESET_TOKEN_EXPIRE_HOURS
    subject = f"Reset your {app_name} password"

    plain_text = (
        f"Hello,\n\n"
        f"We received a request to reset the password for your {app_name} account ({to_email}).\n\n"
        f"To choose a new password, open the HTML version of this email and click the "
        f"\"Click here\" link.\n\n"
        f"This link will expire in {expire_hours} hour(s) for your security.\n\n"
        f"If you did not request a password reset, you can safely ignore this email. "
        f"Your password will stay the same.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      We received a request to reset the password for your
      <strong style="color: #111827;">{app_name}</strong> account
      (<strong style="color: #111827;">{to_email}</strong>).
    </p>
    <p style="margin: 0 0 20px; font-size: 15px; line-height: 1.7; color: #374151;">
      To continue, use the secure link below to choose a new password.
      This link is valid for <strong style="color: #111827;">{expire_hours} hour(s)</strong>.
    </p>
    <p style="margin: 0 0 24px; font-size: 15px; line-height: 1.7; color: #374151;">
      <a
        href="{reset_url}"
        style="
          color: #2563eb;
          font-weight: 700;
          text-decoration: underline;
          background-color: #eff6ff;
          padding: 2px 4px;
          border-radius: 4px;
        "
      >
        Click here
      </a>
      to reset your password.
    </p>
    <p style="margin: 0 0 16px; font-size: 14px; line-height: 1.7; color: #6b7280;">
      If you did not request a password reset, you can safely ignore this email.
      Your password will stay the same.
    </p>
    <p style="margin: 0; font-size: 15px; line-height: 1.7; color: #374151;">
      Thanks,<br />
      <strong style="color: #111827;">The {app_name} Team</strong>
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Reset your {app_name} password using the secure link in this email.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)


def build_password_recovery_email(*, to_email: str, otp_code: str) -> EmailContent:
    """Build the HTML/plain password recovery email for player forgot-password."""
    app_name = _display_app_name()
    expire_minutes = settings.PASSWORD_RECOVERY_OTP_EXPIRE_MINUTES
    subject = f"Reset your {app_name} password"

    plain_text = (
        f"Hello,\n\n"
        f"We received a request to reset the password for your {app_name} account.\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in {expire_minutes} minute(s).\n\n"
        f"If you did not request a password reset, you can safely ignore this email.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      We received a request to reset the password for your
      <strong style="color: #111827;">{app_name}</strong> account
      (<strong style="color: #111827;">{to_email}</strong>).
      Use the verification code below to continue.
    </p>
    <p style="margin: 0 0 20px; font-size: 28px; line-height: 1.4; letter-spacing: 6px; color: #111827; font-weight: 700;">
      {otp_code}
    </p>
    <p style="margin: 0 0 16px; font-size: 14px; line-height: 1.7; color: #6b7280;">
      This code expires in <strong style="color: #111827;">{expire_minutes} minute(s)</strong>.
    </p>
    <p style="margin: 0; font-size: 15px; line-height: 1.7; color: #374151;">
      Thanks,<br />
      <strong style="color: #111827;">The {app_name} Team</strong>
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Your {app_name} password recovery code is {otp_code}.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)


def build_email_verification_email(*, to_email: str, otp_code: str) -> EmailContent:
    """Build the HTML/plain verification email sent after coach registration."""
    app_name = _display_app_name()
    expire_minutes = settings.EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES
    subject = f"Verify your {app_name} email"

    plain_text = (
        f"Hello,\n\n"
        f"Thank you for registering with {app_name}.\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in {expire_minutes} minute(s).\n\n"
        f"If you did not create an account, you can safely ignore this email.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      Thank you for registering with <strong style="color: #111827;">{app_name}</strong>.
      Use the verification code below to confirm your email address
      (<strong style="color: #111827;">{to_email}</strong>).
    </p>
    <p style="margin: 0 0 20px; font-size: 28px; line-height: 1.4; letter-spacing: 6px; color: #111827; font-weight: 700;">
      {otp_code}
    </p>
    <p style="margin: 0 0 16px; font-size: 14px; line-height: 1.7; color: #6b7280;">
      This code expires in <strong style="color: #111827;">{expire_minutes} minute(s)</strong>.
    </p>
    <p style="margin: 0; font-size: 15px; line-height: 1.7; color: #374151;">
      Thanks,<br />
      <strong style="color: #111827;">The {app_name} Team</strong>
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Your {app_name} verification code is {otp_code}.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)


def build_subscription_price_change_email(
    *,
    plan_name: str,
    old_price: str,
    new_price: str,
    billing_frequency: str,
) -> EmailContent:
    app_name = _display_app_name()
    subject = f"Your {app_name} subscription price has been updated"

    plain_text = (
        f"Hello,\n\n"
        f"The price for your {plan_name} subscription ({billing_frequency}) has been updated.\n\n"
        f"Previous price: {old_price}\n"
        f"New price: {new_price}\n\n"
        f"Your subscription has been automatically moved to the new price. "
        f"No action is required on your part.\n\n"
        f"If you have questions, please contact support.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      The price for your <strong style="color: #111827;">{plan_name}</strong>
      subscription ({billing_frequency}) has been updated.
    </p>
    <table
      role="presentation"
      cellspacing="0"
      cellpadding="0"
      style="margin: 0 0 20px; border-collapse: collapse;"
    >
      <tr>
        <td style="padding: 8px 16px 8px 0; font-size: 14px; color: #6b7280;">Previous price</td>
        <td style="padding: 8px 0; font-size: 14px; color: #111827; font-weight: 600;">{old_price}</td>
      </tr>
      <tr>
        <td style="padding: 8px 16px 8px 0; font-size: 14px; color: #6b7280;">New price</td>
        <td style="padding: 8px 0; font-size: 14px; color: #111827; font-weight: 600;">{new_price}</td>
      </tr>
    </table>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      Your subscription has been automatically moved to the new price.
      No action is required on your part.
    </p>
    <p style="margin: 0; font-size: 15px; line-height: 1.7; color: #374151;">
      Thanks,<br />
      <strong style="color: #111827;">The {app_name} Team</strong>
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Your {plan_name} subscription price changed from {old_price} to {new_price}.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)


def build_subscription_plan_archived_email(
    *,
    plan_name: str,
    billing_frequency: str,
    period_end: str | None,
    replacement_plan_name: str | None,
) -> EmailContent:
    app_name = _display_app_name()
    subject = f"Your {app_name} {plan_name} plan is being archived"

    if replacement_plan_name and period_end:
        change_text = (
            f"You can keep using {plan_name} until {period_end}. "
            f"After that, your subscription will automatically move to {replacement_plan_name}."
        )
    elif period_end:
        change_text = (
            f"You can keep using {plan_name} until {period_end}. "
            "No action is required on your part."
        )
    elif replacement_plan_name:
        change_text = (
            f"Your subscription will automatically move to {replacement_plan_name} "
            "at the end of your current billing period."
        )
    else:
        change_text = (
            "You can keep using your current plan until the end of your billing period. "
            "No action is required on your part."
        )

    plain_text = (
        f"Hello,\n\n"
        f"The {plan_name} subscription ({billing_frequency}) is no longer available "
        f"for new customers.\n\n"
        f"{change_text}\n\n"
        f"If you have questions, please contact support.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      The <strong style="color: #111827;">{plan_name}</strong> subscription
      ({billing_frequency}) is no longer available for new customers.
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      {change_text}
    </p>
    <p style="margin: 0; font-size: 15px; line-height: 1.7; color: #374151;">
      Thanks,<br />
      <strong style="color: #111827;">The {app_name} Team</strong>
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Your {plan_name} plan is archived for new customers.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)


def build_coach_invite_email(
    *,
    to_email: str,
    organization_name: str,
    invite_url: str,
) -> EmailContent:
    """Build the HTML/plain coach invitation email for organization admins."""
    app_name = _display_app_name()
    subject = f"You've been invited to join {organization_name} on {app_name}"

    plain_text = (
        f"Hello,\n\n"
        f"You have been invited to join {organization_name} as a coach on {app_name}.\n\n"
        f"Open this link to accept your invitation:\n{invite_url}\n\n"
        f"If you were not expecting this invitation, you can ignore this email.\n\n"
        f"Thanks,\n"
        f"The {app_name} Team"
    )

    body_html = f"""
    <p style="margin: 0 0 16px; font-size: 16px; line-height: 1.7; color: #111827;">
      Hello,
    </p>
    <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.7; color: #374151;">
      You have been invited to join
      <strong style="color: #111827;">{organization_name}</strong> as a coach on
      <strong style="color: #111827;">{app_name}</strong>.
    </p>
    <p style="margin: 0 0 24px; font-size: 15px; line-height: 1.7; color: #374151;">
      <a
        href="{invite_url}"
        style="
          color: #2563eb;
          font-weight: 700;
          text-decoration: underline;
          background-color: #eff6ff;
          padding: 2px 4px;
          border-radius: 4px;
        "
      >
        Accept invitation
      </a>
    </p>
    <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #6b7280;">
      If you were not expecting this invitation, you can safely ignore this email.
    </p>
    """

    html = render_email(
        title=subject,
        body_html=body_html,
        preview_text=f"Accept your coach invitation to join {organization_name}.",
    )

    return EmailContent(subject=subject, plain_text=plain_text, html=html)
