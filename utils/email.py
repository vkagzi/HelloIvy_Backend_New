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
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 40px 32px; background-color: #ffffff;">
      <div style="text-align: center; margin-bottom: 28px;">
        <span style="font-size: 26px; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px;">hello<span style="color: #6c3be4;">ivy</span></span>
      </div>
      <h2 style="color: #1a1a2e; font-size: 20px; font-weight: 700; margin-bottom: 8px;">Your OTP Code &#128274;</h2>
      <p style="color: #555555; font-size: 15px; margin-bottom: 24px;">Use the following one-time password (OTP) to complete your verification:</p>
      <div style="background: linear-gradient(135deg, #6c3be4, #4f46e5); border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
        <span style="font-size: 42px; font-weight: 800; letter-spacing: 14px; color: #ffffff;">{otp_code}</span>
      </div>
      <p style="color: #555555; font-size: 14px; margin-bottom: 8px;">This code is valid for <strong>10 minutes</strong>. For your security, do not share this code with anyone.</p>
      <p style="color: #888888; font-size: 13px;">If you didn&rsquo;t request this code, you can safely ignore this email.</p>
      <hr style="border: none; border-top: 1px solid #eeeeee; margin: 28px 0;" />
      <p style="color: #aaaaaa; font-size: 12px; text-align: center;">HelloIvy &mdash; AI-Powered Career Guidance</p>
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
    send_email(to, subject, template_id=template_id, dynamic_template_data=dynamic_template_data)


def send_payment_pending_email(
    email: str,
    user_name: str,
    transaction_id: str,
    payment_date: str,
    modules: list[dict],
    total_amount: str,
    currency: str = "INR",
    invoice_pdf: bytes | None = None,
) -> None:
    """Send payment pending notification email."""
    to = email
    subject = "Payment Pending – HelloIvy.ai"
    print(f"[EMAIL] Sending payment pending to {to}")
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 32px; background: #ffffff; border: 1px solid #eeeeee; border-radius: 16px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <span style="font-size: 28px; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px;">hello<span style="color: #7B0012;">ivy</span></span>
      </div>
      
      <h2 style="color: #1a1a2e; font-size: 22px; font-weight: 700; margin-bottom: 12px;">Payment Pending &#8987;</h2>
      <p style="color: #555; font-size: 15px; line-height: 1.6;">Hi <strong>{user_name}</strong>,</p>
      <p style="color: #555; font-size: 15px; line-height: 1.6;">Your payment for HelloIvy modules is currently pending. This can happen if the payment gateway is taking a bit longer to confirm the transaction.</p>
      
      <div style="margin-top: 24px; padding: 20px; background: #f9fafb; border-radius: 12px; border: 1px solid #edf2f7;">
        <p style="margin: 0 0 8px; font-size: 14px; color: #718096;">Transaction Detail</p>
        <p style="margin: 0 0 4px; font-size: 14px; color: #1a1a2e;"><strong>Order ID:</strong> {transaction_id}</p>
        <p style="margin: 0 0 4px; font-size: 14px; color: #1a1a2e;"><strong>Amount:</strong> {total_amount} {currency}</p>
        <p style="margin: 0; font-size: 14px; color: #1a1a2e;"><strong>Date:</strong> {payment_date}</p>
      </div>

      <p style="color: #555; font-size: 15px; line-height: 1.6; margin-top: 24px;">Don't worry! We'll automatically update your account once the payment is confirmed. If the amount was debited from your account but remains pending for more than 24 hours, please contact us.</p>

      <div style="margin-top: 32px; text-align: center;">
        <a href="https://helloivy.ai" style="display: inline-block; padding: 12px 32px; background: #7B0012; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 8px; font-size: 15px;">Check Status</a>
      </div>

      <hr style="border: none; border-top: 1px solid #eee; margin: 28px 0;" />
      <p style="color: #aaa; font-size: 12px; text-align: center;">HelloIvy &mdash; AI-Powered Career Guidance</p>
    </div>
    """
    send_email(to, subject, html=html)


def send_chatbot_report_email(
    email: str,
    student_name: str,
    module_name: str,
    transcript: list[dict],
    recommendations: list[dict] = None,
    session_id: str = None,
    report_pdf: bytes | None = None
) -> None:
    """Send chatbot conversation transcript and report to the student."""
    to = email
    subject = f"Your {module_name} Report – HelloIvy.ai"
    print(f"[EMAIL] Sending chatbot report to {to}")

    # Format transcript
    transcript_html = ""
    for msg in transcript:
        # Handle paired messages (Service structure)
        bot_q = msg.get('bot_question') or msg.get('content')
        user_a = msg.get('student_response') or ""
        
        if bot_q:
            transcript_html += f"""
            <div style="margin-bottom: 20px; padding: 16px; background-color: #f9f9f9; border-left: 4px solid #7B0012; border-radius: 8px;">
                <p style="margin: 0 0 4px; font-size: 11px; font-weight: bold; color: #7B0012; text-transform: uppercase;">AI Coach</p>
                <p style="margin: 0 0 12px; font-size: 14px; color: #333; line-height: 1.5; font-style: italic;">"{bot_q}"</p>
            """
            if user_a:
                transcript_html += f"""
                <p style="margin: 0 0 4px; font-size: 11px; font-weight: bold; color: #4f46e5; text-transform: uppercase;">You</p>
                <p style="margin: 0; font-size: 14px; color: #333; line-height: 1.5;">{user_a}</p>
                """
            transcript_html += "</div>"

    # Format recommendations
    recommendations_html = ""
    if recommendations:
        recommendations_html += """
        <div style="margin-top: 32px; padding: 24px; background: #fffafb; border: 1px solid #ffe4e8; border-radius: 12px;">
            <h3 style="margin: 0 0 16px; color: #7B0012; font-size: 18px;">Key Recommendations</h3>
        """
        for rec in recommendations:
            title = rec.get('career_title') or rec.get('domain_title') or rec.get('university_name') or "Recommendation"
            match = rec.get('match_percentage', 0)
            description = rec.get('description', '')
            
            recommendations_html += f"""
            <div style="margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #eee;">
                <p style="margin: 0 0 4px; font-size: 15px; font-weight: bold; color: #1a1a2e;">{title} <span style="float: right; font-size: 13px; color: #059669;">{match}% Match</span></p>
                <p style="margin: 0; font-size: 13px; color: #555;">{description}</p>
            </div>
            """
        recommendations_html += "</div>"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 32px; background: #ffffff; border: 1px solid #eeeeee; border-radius: 16px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <span style="font-size: 28px; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px;">hello<span style="color: #7B0012;">ivy</span></span>
      </div>
      
      <h2 style="color: #1a1a2e; font-size: 22px; font-weight: 700; margin-bottom: 12px;">Your {module_name} Report is Ready! &#127881;</h2>
      <p style="color: #555; font-size: 15px; line-height: 1.6;">Hi <strong>{student_name}</strong>,</p>
      <p style="color: #555; font-size: 15px; line-height: 1.6;">Great job completing your discovery session! We've compiled your conversation and top recommendations below so you can refer back to them anytime.</p>

      {recommendations_html}

      <div style="margin-top: 32px;">
        <h3 style="color: #1a1a2e; font-size: 18px; margin-bottom: 16px; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px;">Conversation History</h3>
        {transcript_html}
      </div>

      <div style="margin-top: 32px; text-align: center; padding: 24px; background: #f9fafb; border-radius: 12px;">
        <p style="margin: 0 0 16px; font-size: 14px; color: #555;">You can also view your full interactive report on the HelloIvy dashboard.</p>
        <a href="https://helloivy.ai" style="display: inline-block; padding: 12px 32px; background: #7B0012; color: #ffffff; text-decoration: none; font-weight: bold; border-radius: 8px; font-size: 15px;">Go to Dashboard</a>
      </div>

      <p style="color: #888; font-size: 13px; margin-top: 32px; text-align: center;">Best of luck with your journey!</p>
      <hr style="border: none; border-top: 1px solid #eee; margin: 28px 0;" />
      <p style="color: #aaa; font-size: 12px; text-align: center;">HelloIvy &mdash; AI-Powered Career Guidance</p>
    </div>
    """

    attachments = None
    if report_pdf:
        attachments = [{
            "content": report_pdf,
            "filename": f"HelloIvy_{module_name.replace(' ', '_')}_Report_{session_id}.pdf",
            "mime_type": "application/pdf",
        }]

    send_email(to, subject, html=html, attachments=attachments)


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
    # Subject is required for plain HTML emails but templates supply their own
    if not template_id and not subject:
        logger.warning("[EMAIL] Subject is required for non-template emails; skipping email send.")
        return
    if not template_id and not html:
        logger.warning("[EMAIL] No template or HTML content provided; skipping email send.")
        return

    logger.info(f"[EMAIL] Attempting to send email to={to}, subject={subject!r}, template_id={template_id}")
    if dynamic_template_data:
        logger.info(f"[EMAIL] dynamic_template_data={dynamic_template_data}")

    try:
        from_email = Email(SENDGRID_FROM_EMAIL, name=SENDGRID_FROM_NAME)

        if template_id:
            # Use dynamic template — subject/html_content are driven by the template itself
            message = Mail(from_email=from_email, to_emails=to)
            message.template_id = template_id
            if dynamic_template_data:
                message.dynamic_template_data = dynamic_template_data
        else:
            # Plain HTML email
            message = Mail(
                from_email=from_email,
                to_emails=to,
                subject=subject,
                html_content=html,
            )

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
