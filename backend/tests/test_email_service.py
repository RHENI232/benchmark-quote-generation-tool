"""
Unit tests for backend.app.services.email_service.

Verifies:
1. Message construction and dynamic escaping.
2. Console delivery mode.
3. Gmail SMTP delivery with mocked smtplib.
4. Error handling for auth failures, connection errors, and missing credentials.
5. Zero real SMTP calls occur in tests.
"""

import smtplib
import ssl
from unittest.mock import MagicMock, patch
import pytest

from backend.app.core.config import settings
from backend.app.services.email_service import (
    build_invitation_message,
    send_invitation_email,
    EmailConfigError,
    EmailAuthError,
    EmailConnectionError,
    EmailDeliveryError,
)


def test_build_invitation_message_structure():
    """Verify headers, plain text, and HTML formatting in EmailMessage."""
    recipient = "newuser@benchmark.local"
    url = "http://localhost:5173/invite/accept?token=xyz123abc"
    role = "Sales"

    msg = build_invitation_message(recipient, url, role)

    assert msg["To"] == recipient
    assert "Benchmark Broadcast Systems" in msg["From"]
    assert "Invitation" in msg["Subject"]

    # Verify plain text body
    body_text = msg.get_body(preferencelist=("plain",)).get_content()
    assert url in body_text
    assert "72 hours" in body_text
    assert "Sales" in body_text

    # Verify HTML body and escaping
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert url in html_body
    assert "Accept your invitation" in html_body
    assert "72 hours" in html_body
    assert "<strong>Sales</strong>" in html_body


def test_build_invitation_message_html_escaping():
    """Verify that dangerous HTML characters in recipient and URL are escaped."""
    recipient = 'test<script>alert("xss")</script>@test.com'
    url = 'http://localhost:5173/invite/accept?token=a&b="test"&c=<tag>'

    msg = build_invitation_message(recipient, url)
    html_body = msg.get_body(preferencelist=("html",)).get_content()

    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body
    assert "<tag>" not in html_body
    assert "&lt;tag&gt;" in html_body


def test_send_invitation_email_console_provider(capsys, monkeypatch):
    """Console provider prints message details and does not attempt network calls."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")

    recipient = "console_user@test.local"
    url = "http://localhost:5173/invite/accept?token=console-token-123"

    send_invitation_email(recipient, url)

    captured = capsys.readouterr()
    assert "[CONSOLE EMAIL DELIVERY]" in captured.out
    assert recipient in captured.out
    assert url in captured.out


def test_send_invitation_email_gmail_success(monkeypatch):
    """Gmail provider connects via STARTTLS, authenticates, and sends message."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret-app-password")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "sender@gmail.com")

    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", mock_smtp_class):
        send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587, timeout=15.0)
        assert mock_smtp_instance.ehlo.call_count == 2
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("sender@gmail.com", "secret-app-password")
        mock_smtp_instance.send_message.assert_called_once()


def test_send_invitation_email_gmail_missing_credentials(monkeypatch):
    """Missing SMTP credentials raises EmailConfigError."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")

    with pytest.raises(EmailConfigError) as exc_info:
        send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

    assert "credentials are not configured" in str(exc_info.value)


def test_send_invitation_email_gmail_auth_failure(monkeypatch):
    """SMTPAuthenticationError raises EmailAuthError without exposing secrets."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "wrong-app-password")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(EmailAuthError) as exc_info:
            send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        assert "authentication failed" in str(exc_info.value).lower()
        assert "wrong-app-password" not in str(exc_info.value)


def test_send_invitation_email_gmail_connection_failure(monkeypatch):
    """Connection errors raise EmailConnectionError."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
        with pytest.raises(EmailConnectionError) as exc_info:
            send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        assert "connect" in str(exc_info.value).lower()


def test_send_invitation_email_gmail_tls_failure(monkeypatch):
    """TLS negotiation failure raises EmailConnectionError with TLS detail."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.starttls.side_effect = ssl.SSLError("TLS handshake failed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(EmailConnectionError) as exc_info:
            send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        assert "tls" in str(exc_info.value).lower()


def test_send_invitation_email_gmail_auth_server_disconnected(monkeypatch):
    """Server disconnect during login (Gmail 535 BadCredentials drop) raises EmailAuthError."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.login.side_effect = smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(EmailAuthError) as exc_info:
            send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        assert "server disconnected" in str(exc_info.value).lower() or "authentication failed" in str(exc_info.value).lower()


def test_send_invitation_email_gmail_message_delivery_failure(monkeypatch):
    """Failure during send_message raises EmailDeliveryError."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "gmail")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.send_message.side_effect = smtplib.SMTPDataError(550, b"Mailbox unavailable")

    with patch("smtplib.SMTP", return_value=mock_smtp_instance):
        with pytest.raises(EmailDeliveryError) as exc_info:
            send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

        assert "message delivery failed" in str(exc_info.value).lower()


def test_send_invitation_email_invalid_provider(monkeypatch):
    """Unsupported provider raises EmailConfigError."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid_unsupported")

    with pytest.raises(EmailConfigError) as exc_info:
        send_invitation_email("recipient@domain.com", "http://localhost:5173/invite/accept?token=tok")

    assert "Unsupported EMAIL_PROVIDER" in str(exc_info.value)
