"""
Email Service for Benchmark Broadcast Systems — Presales Quote Tool.

Supports:
1. Console delivery for local development and testing.
2. Gmail SMTP delivery with TLS and App Password authentication.
"""

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Base exception for email delivery failures."""
    pass


class EmailConfigError(EmailDeliveryError):
    """Raised when email settings are missing or misconfigured."""
    pass


class EmailConnectionError(EmailDeliveryError):
    """Raised when connecting to the SMTP server fails."""
    pass


class EmailAuthError(EmailDeliveryError):
    """Raised when SMTP authentication fails."""
    pass


def build_invitation_message(
    recipient_email: str,
    invitation_url: str,
    role_tier: Optional[str] = None
) -> EmailMessage:
    """
    Construct a multipart plain-text and HTML invitation email using Python's EmailMessage.
    """
    from_name = settings.SMTP_FROM_NAME or "Benchmark Broadcast Systems"
    from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME or "noreply@benchmarkbroadcast.com"
    role_display = f" as {role_tier}" if role_tier else ""

    msg = EmailMessage()
    msg["Subject"] = "Invitation to Benchmark Broadcast Systems — Presales Quote Tool"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = recipient_email

    # Plain text version
    plain_text = f"""Hello,

You have been invited to join the Benchmark Broadcast Systems — Presales Quote Tool{role_display}.

To activate your account and set your password, please open the following link in your browser:
{invitation_url}

This invitation link will expire in 72 hours.

If you were not expecting this invitation, you can safely ignore this email.

Best regards,
Benchmark Broadcast Systems
"""
    msg.set_content(plain_text)

    # HTML version
    safe_url = html.escape(invitation_url)
    safe_email = html.escape(recipient_email)
    safe_role = f" as <strong>{html.escape(role_tier)}</strong>" if role_tier else ""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      background-color: #f8fafc;
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 580px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    .header {{
      background-color: #0f172a;
      padding: 24px;
      text-align: center;
      color: #ffffff;
    }}
    .header h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
    .content {{
      padding: 32px 24px;
    }}
    .content p {{
      margin: 0 0 16px;
      line-height: 1.6;
      font-size: 15px;
    }}
    .button-container {{
      text-align: center;
      margin: 28px 0;
    }}
    .button {{
      background-color: #2563eb;
      color: #ffffff !important;
      padding: 12px 28px;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
      display: inline-block;
    }}
    .link-fallback {{
      font-size: 13px;
      color: #64748b;
      word-break: break-all;
      margin-top: 24px;
      background-color: #f8fafc;
      padding: 12px;
      border-radius: 4px;
      border: 1px solid #e2e8f0;
    }}
    .footer {{
      background-color: #f1f5f9;
      padding: 16px 24px;
      text-align: center;
      font-size: 12px;
      color: #64748b;
      border-top: 1px solid #e2e8f0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Benchmark Broadcast Systems</h1>
    </div>
    <div class="content">
      <p>Hello <strong>{safe_email}</strong>,</p>
      <p>You have been invited to join the <strong>Benchmark Broadcast Systems — Presales Quote Tool</strong>{safe_role}.</p>
      <p>Click the button below to set up your password and activate your account:</p>
      <div class="button-container">
        <a href="{safe_url}" class="button" target="_blank" rel="noopener noreferrer">Accept your invitation</a>
      </div>
      <p>This invitation link will expire in <strong>72 hours</strong>.</p>
      <div class="link-fallback">
        <p style="margin: 0 0 6px; font-weight: 600;">Can't click the button? Copy and paste this link into your browser:</p>
        <p style="margin: 0;"><a href="{safe_url}" style="color: #2563eb;">{safe_url}</a></p>
      </div>
      <p style="margin-top: 24px; font-size: 13px; color: #64748b;">If you were not expecting this invitation, you can safely ignore this email.</p>
    </div>
    <div class="footer">
      &copy; Benchmark Broadcast Systems. All rights reserved.
    </div>
  </div>
</body>
</html>
"""
    msg.add_alternative(html_content, subtype="html")
    return msg


def _send_via_console(recipient_email: str, invitation_url: str, msg: EmailMessage) -> None:
    """Output invitation email to console/logs for local development."""
    separator = "=" * 70
    output = f"""
{separator}
[CONSOLE EMAIL DELIVERY]
Recipient: {recipient_email}
Subject:   {msg['Subject']}
From:      {msg['From']}

Acceptance Link:
{invitation_url}

Expires in: 72 hours
{separator}
"""
    print(output)
    logger.info(f"[CONSOLE EMAIL] Invitation generated for {recipient_email}. Link: {invitation_url}")


def _send_via_gmail(recipient_email: str, msg: EmailMessage) -> None:
    """Send invitation email using Gmail SMTP with STARTTLS and App Password."""
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise EmailConfigError(
            "Gmail SMTP credentials are not configured. "
            "Please set SMTP_USERNAME and SMTP_PASSWORD in your .env file."
        )

    host = settings.SMTP_HOST or "smtp.gmail.com"
    port = settings.SMTP_PORT or 587
    timeout = 15.0
    server = None

    try:
        # Stage 1: TCP connection
        logger.debug(f"[SMTP DIAGNOSTIC] Initiating TCP connection to {host}:{port} (timeout={timeout}s)")
        try:
            server = smtplib.SMTP(host, port, timeout=timeout)
        except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'TCP connection' to {host}:{port}: {type(e).__name__}: {e}")
            raise EmailConnectionError(
                f"Failed to connect to Gmail SMTP server ({host}:{port}). Please check network connectivity and firewall settings."
            ) from e

        # Stage 2: Initial EHLO
        logger.debug(f"[SMTP DIAGNOSTIC] Executing initial EHLO with {host}:{port}")
        try:
            server.ehlo()
        except smtplib.SMTPException as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'Initial EHLO': {type(e).__name__}: {e}")
            raise EmailConnectionError(f"SMTP greeting failed with Gmail server ({host}:{port}).") from e

        # Stage 3: STARTTLS negotiation
        logger.debug("[SMTP DIAGNOSTIC] Initiating STARTTLS with verified SSL context")
        try:
            context = ssl.create_default_context()
            server.starttls(context=context)
        except (ssl.SSLError, smtplib.SMTPException, OSError) as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'STARTTLS': {type(e).__name__}: {e}")
            raise EmailConnectionError(f"TLS security negotiation failed with Gmail SMTP server ({host}:{port}).") from e

        # Stage 4: Second EHLO (post-TLS)
        logger.debug(f"[SMTP DIAGNOSTIC] Executing post-TLS EHLO with {host}:{port}")
        try:
            server.ehlo()
        except smtplib.SMTPException as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'Post-TLS EHLO': {type(e).__name__}: {e}")
            raise EmailConnectionError(f"Post-TLS greeting failed with Gmail server ({host}:{port}).") from e

        # Stage 5: SMTP Authentication
        logger.debug(f"[SMTP DIAGNOSTIC] Authenticating as '{settings.SMTP_USERNAME}'")
        try:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'SMTP authentication': {type(e).__name__} (code={e.smtp_code}): {e.smtp_error}")
            raise EmailAuthError(
                "Gmail SMTP authentication failed. Please verify that SMTP_USERNAME is correct "
                "and that SMTP_PASSWORD is an active 16-character Google App Password (not your standard account password)."
            ) from e
        except smtplib.SMTPServerDisconnected as e:
            # Gmail actively terminates connection when authentication credentials (e.g. AUTH PLAIN) are rejected
            logger.error(
                f"[SMTP DIAGNOSTIC] Failed at stage 'SMTP authentication': Server disconnected unexpectedly. "
                "Gmail closes the connection when authentication credentials are rejected (BadCredentials)."
            )
            raise EmailAuthError(
                "Gmail SMTP authentication failed: server disconnected during login. "
                "Please verify that SMTP_USERNAME is correct and that you are using a 16-character Google App Password."
            ) from e
        except (smtplib.SMTPException, OSError) as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'SMTP authentication': {type(e).__name__}: {e}")
            raise EmailAuthError(
                "Gmail SMTP authentication failed. Please verify your credentials and Google App Password settings."
            ) from e

        # Stage 6: Message Submission
        logger.debug(f"[SMTP DIAGNOSTIC] Submitting invitation email for '{recipient_email}'")
        try:
            server.send_message(msg)
            logger.info(f"Successfully sent invitation email to {recipient_email} via Gmail SMTP.")
        except (smtplib.SMTPException, OSError) as e:
            logger.error(f"[SMTP DIAGNOSTIC] Failed at stage 'Message submission': {type(e).__name__}: {e}")
            raise EmailDeliveryError(f"SMTP message delivery failed: {e}") from e

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass


def send_invitation_email(
    recipient_email: str,
    invitation_url: str,
    role_tier: Optional[str] = None
) -> None:
    """
    Public entrypoint to dispatch an invitation email according to EMAIL_PROVIDER setting.
    """
    msg = build_invitation_message(recipient_email, invitation_url, role_tier)
    provider = (settings.EMAIL_PROVIDER or "console").strip().lower()

    if provider == "console":
        _send_via_console(recipient_email, invitation_url, msg)
    elif provider == "gmail":
        _send_via_gmail(recipient_email, msg)
    else:
        raise EmailConfigError(f"Unsupported EMAIL_PROVIDER '{settings.EMAIL_PROVIDER}'. Use 'console' or 'gmail'.")
