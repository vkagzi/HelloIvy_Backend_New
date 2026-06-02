import base64
import logging
import environ
import ssl
import certifi
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Attachment, FileContent, FileName, FileType, Disposition

logger = logging.getLogger(__name__)

env = environ.Env()
SENDGRID_API_KEY = env("SENDGRID_API_KEY", None)
SENDGRID_FROM_EMAIL = env("SENDGRID_FROM_EMAIL", default=None)
SENDGRID_FROM_NAME = env("SENDGRID_FROM_NAME", default="HelloIvy")

# Fix SSL certificate verification issues
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()


def send_otp_email(email: str, otp_code: str) -> None:
    """Send OTP email for registration or password reset."""
    to = email
    subject = "Your HelloIvy OTP Code"
    print(f"[EMAIL] Sending OTP to {to}: {otp_code}")
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h2 style="color: #6c3be4;">Your OTP Code</h2>
      <p>Use the code below to verify your email address:</p>
      <div style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #6c3be4; padding: 16px 0;">
        {otp_code}
      </div>
      <p style="color: #666; font-size: 13px;">This code expires in 10 minutes. Do not share it with anyone.</p>
      <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
      <p style="color: #999; font-size: 12px;">HelloIvy &mdash; AI-Powered Career Guidance</p>
    </div>
    """
    send_email(to, subject, html=html)


def send_temp_password_email(email: str, temp_password: str, student_name: str = "") -> None:
    """Send temporary password email for bulk-imported users."""
    to = email
    subject = "Welcome to HelloIvy.ai – Your Temporary Password"
    print(f"[EMAIL] Sending temp password to {to}")
    template_id = "d-6b1a351c2bb14b96b46c45e6e5ab36b9"
    dynamic_template_data = {
        "temp_password": temp_password,
        "student_name": student_name or "there",
        "student_email": email,
    }
    send_email(to, subject, template_id=template_id, dynamic_template_data=dynamic_template_data)


def send_school_admin_welcome_email(email: str, temp_password: str, school_name: str) -> None:
    """Send welcome email when a school admin is added."""
    to = email
    subject = "Welcome to HelloIvy.ai – School Admin Account"
    print(f"[EMAIL] Sending school admin welcome to {to}")
    template_id = "d-e1de64adeb30437c8f7b49ef745a32fa"
    dynamic_template_data = {
        "temp_password": temp_password,
        "school_name": school_name,
        "admin_email": email,
    }
    send_email(to, subject, template_id=template_id, dynamic_template_data=dynamic_template_data)


def send_payment_success_email(
    email: str,
    user_name: str,
    transaction_id: str,
    payment_date: str,
    modules: list[dict],
    subtotal: str,
    tax: str,
    total_amount: str,
    currency: str = "INR",
    discount: str | None = None,
    payment_method: str = "HDFC Gateway",
    tax_label: str = "GST (18%)",
    invoice_pdf: bytes | None = None,
) -> None:
    """Send payment success confirmation email."""
    to = email
    subject = "Payment Successful – HelloIvy.ai"
    print(f"[EMAIL] Sending payment success to {to}")
    template_id = "d-0f313686970742ac85dad0aadeae1d68"
    dynamic_template_data = {
        "user_name": user_name or "there",
        "transaction_id": transaction_id,
        "payment_date": payment_date,
        "payment_method": payment_method,
        "modules": modules,
        "subtotal": subtotal,
        "tax": tax,
        "tax_label": tax_label,
        "total_amount": total_amount,
        "currency": currency,
    }
    if discount:
        dynamic_template_data["discount"] = discount

    attachments = None
    if invoice_pdf:
        attachments = [{
            "content": invoice_pdf,
            "filename": f"HelloIvy_Invoice_{transaction_id}.pdf",
            "mime_type": "application/pdf",
        }]
    send_email(to, subject, template_id=template_id, dynamic_template_data=dynamic_template_data, attachments=attachments)


def send_payment_failed_email(
    email: str,
    user_name: str,
    transaction_id: str,
    payment_date: str,
    modules: list[dict],
    total_amount: str,
    currency: str = "INR",
    failure_reason: str | None = None,
) -> None:
    """Send payment failure notification email."""
    to = email
    subject = "Payment Failed – HelloIvy.ai"
    print(f"[EMAIL] Sending payment failed to {to}")
    template_id = "d-5016dd8729f74359b2dc84c5bb20ccb0"
    dynamic_template_data = {
        "user_name": user_name or "there",
        "transaction_id": transaction_id,
        "payment_date": payment_date,
        "modules": modules,
        "total_amount": total_amount,
        "currency": currency,
    }
    if failure_reason:
        dynamic_template_data["failure_reason"] = failure_reason
    send_email(to, subject, template_id=template_id, dynamic_template_data=dynamic_template_data)


def send_email(
    to: str,
    subject: str,
    template_id: str | None = None,
    dynamic_template_data: dict | None = None,
    html: str | None = None,
    attachments: list[dict] | None = None,
) -> None:
    """Send email using SendGrid."""
    if not SENDGRID_API_KEY:
        logger.warning("[EMAIL] SENDGRID_API_KEY is not configured; skipping email send.")
        return
    if not SENDGRID_FROM_EMAIL:
        logger.warning("[EMAIL] SENDGRID_FROM_EMAIL is not configured; skipping email send.")
        return
    if not subject:
        logger.warning("[EMAIL] Subject is required; skipping email send.")
        return
    if not template_id and not html:
        logger.warning("[EMAIL] No template or HTML content provided; skipping email send.")
        return

    logger.info(f"[EMAIL] Attempting to send email to={to}, subject={subject!r}, template_id={template_id}")
    if dynamic_template_data:
        logger.info(f"[EMAIL] dynamic_template_data={dynamic_template_data}")

    try:
        from_email = Email(SENDGRID_FROM_EMAIL, name=SENDGRID_FROM_NAME)
        message = Mail(
            from_email=from_email,
            to_emails=to,
            subject=subject,
            html_content=html
        )
        if template_id:
            message.template_id = template_id
        if dynamic_template_data:
            message.dynamic_template_data = dynamic_template_data

        if attachments:
            for att in attachments:
                encoded = base64.b64encode(att["content"]).decode("ascii")
                attachment = Attachment(
                    FileContent(encoded),
                    FileName(att["filename"]),
                    FileType(att.get("mime_type", "application/octet-stream")),
                    Disposition("attachment"),
                )
                message.attachment = attachment

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        logger.info(f"[EMAIL] SUCCESS: Sent to {to}, status_code={response.status_code}, headers={dict(response.headers)}")
        if response.body:
            logger.info(f"[EMAIL] Response body: {response.body}")

    except Exception as e:
        logger.error(f"[EMAIL] FAILED to send to {to}: {e}")
        
        # PROMINENT CONSOLE FALLBACK
        print("\n" + "="*60)
        print("!!! EMAIL FALLBACK (SendGrid Failed) !!!")
        print(f"TO:      {to}")
        print(f"SUBJECT: {subject}")
        if template_id:
            print(f"TEMPLATE_ID: {template_id}")
        if dynamic_template_data:
            print(f"DYNAMIC_DATA: {dynamic_template_data}")
        if html:
            # Strip simple tags for terminal readability if needed, but here we just show first 500 chars
            print(f"CONTENT (Preview): {html[:500]}...")
        print("="*60 + "\n")
        
        # Don't re-raise if it's a 401/Unauthorized, just log it and allow the process to continue
        # This prevents the whole API request from failing for the user.
        if "401" in str(e) or "Unauthorized" in str(e):
             logger.warning("[EMAIL] Proceeding without sending email due to authentication failure.")
        else:
            # For other errors, we might still want to know, but for local ASAP fix, we suppress and fallback
            logger.warning(f"[EMAIL] Suppressing error and continuing with fallback: {e}")
