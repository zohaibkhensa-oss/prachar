"""Email service — sends transactional emails via Resend (primary) or SMTP (fallback).

Used for:
  - Email verification (welcome email with verification link)
  - Password reset (reset link)
  - (Future) team invitations, billing receipts

If neither RESEND_API_KEY nor SMTP creds are configured, emails are logged
but not sent (dev mode). This lets the app work locally without an email
provider — the verification/reset links are printed to the server log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from prachar_shared.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    to: str
    subject: str
    html: str
    from_email: str = ""
    from_name: str = ""


async def send_email(msg: EmailMessage) -> bool:
    """Send an email. Returns True if sent, False if skipped (dev mode).

    Priority:
      1. Resend API (if RESEND_API_KEY set)
      2. SMTP (if SMTP_HOST set)
      3. Dev mode: log to console (links visible in server output)
    """
    s = get_settings()
    from_addr = msg.from_email or s.email_from
    from_name = msg.from_name or s.email_from_name

    # Option 1: Resend
    if s.resend_api_key:
        try:
            import resend
            resend.api_key = s.resend_api_key
            params: dict = {
                "from": f"{from_name} <{from_addr}>" if from_name else from_addr,
                "to": [msg.to],
                "subject": msg.subject,
                "html": msg.html,
            }
            # resend.send is synchronous; run in thread
            import asyncio
            await asyncio.to_thread(resend.Emails.send, params)
            log.info("Email sent via Resend to %s: %s", msg.to, msg.subject)
            return True
        except Exception as e:
            log.error("Resend send failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 2: SMTP
    if s.smtp_host:
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            message = MIMEMultipart("alternative")
            message["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
            message["To"] = msg.to
            message["Subject"] = msg.subject
            message.attach(MIMEText(msg.html, "html"))

            await aiosmtplib.send(
                message,
                hostname=s.smtp_host,
                port=s.smtp_port,
                username=s.smtp_user or None,
                password=s.smtp_password or None,
                start_tls=True,
            )
            log.info("Email sent via SMTP to %s: %s", msg.to, msg.subject)
            return True
        except Exception as e:
            log.error("SMTP send failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 3: Dev mode — log the email (links visible in server output)
    log.info("📧 [DEV EMAIL] To: %s | Subject: %s", msg.to, msg.subject)
    # Extract any links from the HTML for easy clicking during dev
    import re
    links = re.findall(r'href="(https?://[^"]+)"', msg.html)
    for link in links:
        log.info("📧 [DEV EMAIL LINK] %s", link)
    return False  # Not actually sent, but not an error either


# ─── Email templates ────────────────────────────────────────────────────────

def verification_email_html(verify_url: str, user_name: str = "") -> str:
    name = user_name or "there"
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #6366f1; font-size: 28px; margin: 0;">PRACHAR</h1>
        <p style="color: #6b7280; font-size: 14px; margin-top: 4px;">Your AI marketing agency</p>
      </div>
      <h2 style="color: #111827; font-size: 22px;">Verify your email</h2>
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">
        Hi {name},<br><br>
        Welcome to PRACHAR! Please verify your email address to activate your account and start creating AI-powered marketing campaigns.
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{verify_url}"
           style="background: #6366f1; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: 600; display: inline-block;">
          Verify Email
        </a>
      </div>
      <p style="color: #6b7280; font-size: 14px; line-height: 1.6;">
        Or copy this link into your browser:<br>
        <a href="{verify_url}" style="color: #6366f1; word-break: break-all;">{verify_url}</a>
      </p>
      <p style="color: #6b7280; font-size: 14px; margin-top: 32px;">
        This link expires in 24 hours. If you didn't create an account, you can safely ignore this email.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
      <p style="color: #9ca3af; font-size: 12px;">© 2026 PRACHAR. All rights reserved.</p>
    </div>
    """


def password_reset_email_html(reset_url: str, user_name: str = "") -> str:
    name = user_name or "there"
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #6366f1; font-size: 28px; margin: 0;">PRACHAR</h1>
        <p style="color: #6b7280; font-size: 14px; margin-top: 4px;">Your AI marketing agency</p>
      </div>
      <h2 style="color: #111827; font-size: 22px;">Reset your password</h2>
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">
        Hi {name},<br><br>
        We received a request to reset your PRACHAR password. Click the button below to choose a new password.
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{reset_url}"
           style="background: #6366f1; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-size: 16px; font-weight: 600; display: inline-block;">
          Reset Password
        </a>
      </div>
      <p style="color: #6b7280; font-size: 14px; line-height: 1.6;">
        Or copy this link into your browser:<br>
        <a href="{reset_url}" style="color: #6366f1; word-break: break-all;">{reset_url}</a>
      </p>
      <p style="color: #6b7280; font-size: 14px; margin-top: 32px;">
        This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email — your password won't be changed.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
      <p style="color: #9ca3af; font-size: 12px;">© 2026 PRACHAR. All rights reserved.</p>
    </div>
    """


def verification_success_html() -> str:
    return """
    <div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px; text-align: center;">
      <h1 style="color: #6366f1;">PRACHAR</h1>
      <h2 style="color: #16a34a;">✓ Email verified!</h2>
      <p style="color: #374151; font-size: 16px;">Your email has been verified. You can now log in to your PRACHAR account.</p>
      <a href="/" style="display: inline-block; margin-top: 24px; background: #6366f1; color: white; padding: 12px 28px; border-radius: 8px; text-decoration: none;">Go to PRACHAR</a>
    </div>
    """


def invoice_email_html(invoice_number: str, plan_name: str, total_inr: int, user_name: str = "") -> str:
    name = user_name or "there"
    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h1 style="color: #6366f1; font-size: 28px; margin: 0;">PRACHAR</h1>
        <p style="color: #6b7280; font-size: 14px; margin-top: 4px;">Your AI marketing agency</p>
      </div>
      <h2 style="color: #111827; font-size: 22px;">Payment Receipt</h2>
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">
        Hi {name},<br><br>
        Thank you for your payment! Your subscription has been activated successfully.
      </p>
      <div style="background: #f9fafb; border-radius: 12px; padding: 24px; margin: 24px 0;">
        <table style="width: 100%; border-collapse: collapse; font-size: 15px;">
          <tr>
            <td style="color: #6b7280; padding: 8px 0;">Invoice Number</td>
            <td style="color: #111827; font-weight: 600; text-align: right; padding: 8px 0;">{invoice_number}</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 8px 0;">Plan</td>
            <td style="color: #111827; font-weight: 600; text-align: right; padding: 8px 0;">{plan_name}</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 8px 0;">Amount (incl. GST 18%)</td>
            <td style="color: #111827; font-weight: 600; text-align: right; padding: 8px 0;">Rs. {total_inr:,}</td>
          </tr>
        </table>
      </div>
      <p style="color: #374151; font-size: 16px; line-height: 1.6;">
        Your GST-compliant invoice is attached to this email as a PDF. You can also download it anytime from your <a href="https://app.prachar.app/app/settings" style="color: #6366f1;">Settings &rarr; Billing</a> page.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
      <p style="color: #9ca3af; font-size: 12px;">
        © 2026 PRACHAR AI Technologies | GSTIN: 29ABCDE1234F1Z5 | Bengaluru, India<br>
        This is an automated email. Please do not reply.
      </p>
    </div>
    """


async def send_invoice_email(
    to_email: str,
    invoice_number: str,
    plan_name: str,
    total_inr: int,
    pdf_bytes: bytes,
    user_name: str = "",
) -> bool:
    """Send an invoice email with PDF attachment.

    Uses Resend (with attachment) or SMTP (with MIME attachment).
    Falls back to dev mode (logs to console) if no email provider configured.
    """
    s = get_settings()
    from_addr = s.email_from
    from_name = s.email_from_name
    subject = f"Payment Receipt — {invoice_number}"
    html = invoice_email_html(invoice_number, plan_name, total_inr, user_name)

    # Option 1: Resend (supports attachments)
    if s.resend_api_key:
        try:
            import resend
            resend.api_key = s.resend_api_key
            import asyncio
            params: dict = {
                "from": f"{from_name} <{from_addr}>" if from_name else from_addr,
                "to": [to_email],
                "subject": subject,
                "html": html,
                "attachments": [{
                    "filename": f"{invoice_number}.pdf",
                    "content": list(pdf_bytes),
                }],
            }
            await asyncio.to_thread(resend.Emails.send, params)
            log.info("Invoice email sent via Resend to %s: %s", to_email, invoice_number)
            return True
        except Exception as e:
            log.error("Resend invoice send failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 2: SMTP (with MIME attachment)
    if s.smtp_host:
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.mime.application import MIMEApplication

            message = MIMEMultipart("mixed")
            message["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
            message["To"] = to_email
            message["Subject"] = subject

            # HTML body
            message.attach(MIMEText(html, "html"))

            # PDF attachment
            attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            attachment.add_header("Content-Disposition", "attachment", filename=f"{invoice_number}.pdf")
            message.attach(attachment)

            await aiosmtplib.send(
                message,
                hostname=s.smtp_host,
                port=s.smtp_port,
                username=s.smtp_user or None,
                password=s.smtp_password or None,
                start_tls=True,
            )
            log.info("Invoice email sent via SMTP to %s: %s", to_email, invoice_number)
            return True
        except Exception as e:
            log.error("SMTP invoice send failed: %s: %s", type(e).__name__, str(e)[:200])

    # Option 3: Dev mode — log
    log.info("📧 [DEV EMAIL] Invoice %s to %s (PDF: %d bytes, not sent)", invoice_number, to_email, len(pdf_bytes))
    return False
