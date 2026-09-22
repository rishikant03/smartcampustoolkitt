import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import httpx
except Exception:
    httpx = None

def send_email_otp(to_email: str, otp: str, subject: str = "Your Email Verification OTP") -> tuple[bool, str]:
    """
    Sends a 6-digit verification code to the recipient's email using SMTP.
    Configured via environment variables:
      - SMTP_HOST (or SMTP_SERVER, default: smtp.gmail.com)
      - SMTP_PORT (default: 587)
      - SMTP_EMAIL (or GMAIL_USER)
      - SMTP_PASSWORD (or GMAIL_APP_PASSWORD)
    """
    smtp_server = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_EMAIL") or os.getenv("GMAIL_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD")
    sender_name = os.getenv("SMTP_SENDER_NAME", "AI Student Platform")

    if not smtp_user or not smtp_password:
        msg = "SMTP credentials (SMTP_EMAIL and SMTP_PASSWORD / GMAIL_USER and GMAIL_APP_PASSWORD) not configured in .env."
        print(f"[Notifier] Email Skipped: {msg}")
        print(f"[Notifier] [LOCAL DEV OTP for {to_email}]: {otp}")
        return False, msg

    try:
        # Create MIME message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{smtp_user}>"
        message["To"] = to_email

        text_content = (
            f"Your Email Verification OTP\n\n"
            f"Your OTP is:\n"
            f"{otp}\n\n"
            f"This OTP will expire in 5 minutes.\n"
            f"If you did not request this verification, please safely ignore this email.\n\n"
            f"{sender_name}"
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; margin: 0; padding: 30px; }}
            .card {{ max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); padding: 35px; color: #f8fafc; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .logo {{ font-size: 18px; font-weight: bold; color: #10b981; margin-bottom: 20px; letter-spacing: 1px; }}
            .title {{ font-size: 22px; font-weight: 700; margin-bottom: 12px; color: #ffffff; }}
            .desc {{ font-size: 14px; color: #94a3b8; line-height: 1.5; margin-bottom: 25px; }}
            .otp-box {{ background: rgba(16, 185, 129, 0.12); border: 2px dashed #10b981; border-radius: 12px; padding: 18px 25px; display: inline-block; margin-bottom: 25px; }}
            .otp-code {{ font-size: 38px; font-weight: 800; letter-spacing: 8px; color: #34d399; font-family: monospace; }}
            .expiry-note {{ font-size: 13px; color: #cbd5e1; font-weight: 600; margin-bottom: 15px; }}
            .footer {{ font-size: 12px; color: #64748b; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 20px; margin-top: 20px; }}
          </style>
        </head>
        <body>
          <div class="card">
            <div class="logo">⚡ SMART CAMPUS TOOLKIT</div>
            <div class="title">Your Email Verification OTP</div>
            <div class="desc">Please use the 6-digit verification code below to verify your email address.</div>
            <div class="otp-box">
              <div class="otp-code">{otp}</div>
            </div>
            <div class="expiry-note">This OTP will expire in 5 minutes.</div>
            <div class="footer">If you did not request this OTP, you can safely ignore this email.</div>
          </div>
        </body>
        </html>
        """

        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        # Connect to SMTP server
        with smtplib.SMTP(smtp_server, smtp_port, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], message.as_string())

        print(f"[Notifier] Email successfully sent to {to_email}")
        return True, f"Verification OTP sent to {to_email}"
    except Exception as e:
        error_msg = f"Failed to send email to {to_email}: {str(e)}"
        print(f"[Notifier] {error_msg}")
        return False, error_msg


def send_sms_otp(phone_number: str, otp: str) -> tuple[bool, str]:
    """
    Sends a 6-digit OTP to a mobile phone number via:
      1. Fast2SMS (Indian numbers - FAST2SMS_API_KEY)
      2. Twilio (International - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
      3. Generic Webhook (SMS_WEBHOOK_URL)
    """
    # Clean phone number: remove non-digits except leading '+'
    clean_digits = re.sub(r'[^\d]', '', phone_number)
    
    # Fast2SMS for Indian 10-digit numbers
    fast2sms_key = os.getenv("FAST2SMS_API_KEY")
    if fast2sms_key:
        # If 12 digits starting with 91, take last 10
        indian_num = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
        if len(indian_num) == 10:
            try:
                url = "https://www.fast2sms.com/dev/bulkV2"
                params = {
                    "authorization": fast2sms_key,
                    "variables_values": otp,
                    "route": "otp",
                    "numbers": indian_num
                }
                headers = {"cache-control": "no-cache"}
                with httpx.Client(timeout=10) as client:
                    resp = client.get(url, params=params, headers=headers)
                    data = resp.json()
                    if data.get("return"):
                        print(f"[Notifier] Fast2SMS delivered to {indian_num}")
                        return True, f"SMS delivered to +91 {indian_num}"
                    else:
                        print(f"[Notifier] Fast2SMS error: {data.get('message')}")
                        return False, f"Fast2SMS error: {data.get('message')}"
            except Exception as e:
                print(f"[Notifier] Fast2SMS exception: {e}")
                return False, f"Fast2SMS failed: {str(e)}"

    # Twilio SMS
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_from = os.getenv("TWILIO_PHONE_NUMBER")
    if twilio_sid and twilio_token and twilio_from:
        try:
            # Format to E.164
            to_num = f"+{clean_digits}" if not phone_number.strip().startswith("+") else phone_number.strip()
            # If 10 digits Indian number
            if len(clean_digits) == 10:
                to_num = f"+91{clean_digits}"

            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            data = {
                "From": twilio_from,
                "To": to_num,
                "Body": f"Your AI Student Platform verification code is: {otp}. Valid for 10 minutes."
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, auth=(twilio_sid, twilio_token), data=data)
                if resp.status_code in (200, 201):
                    print(f"[Notifier] Twilio SMS delivered to {to_num}")
                    return True, f"SMS delivered to {to_num}"
                else:
                    err_info = resp.text
                    print(f"[Notifier] Twilio error: {err_info}")
                    return False, f"Twilio SMS failed: {resp.status_code}"
        except Exception as e:
            print(f"[Notifier] Twilio exception: {e}")
            return False, f"Twilio failed: {str(e)}"

    # Generic Webhook
    webhook_url = os.getenv("SMS_WEBHOOK_URL")
    if webhook_url:
        try:
            payload = {
                "phone": phone_number,
                "otp": otp,
                "message": f"Your verification code is: {otp}"
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(webhook_url, json=payload)
                if resp.status_code < 300:
                    return True, "SMS sent via webhook"
        except Exception as e:
            print(f"[Notifier] Webhook SMS failed: {e}")

    msg = "SMS gateway (FAST2SMS_API_KEY or TWILIO) not configured in .env."
    print(f"[Notifier] SMS Skipped: {msg}")
    return False, msg


def send_email_link(to_email: str, link: str, subject: str = "Verify Your Account - AI Student Platform") -> tuple[bool, str]:
    """
    Sends a verification or password reset link to user's email.
    """
    smtp_user = os.getenv("GMAIL_USER") or os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_name = os.getenv("SMTP_SENDER_NAME", "AI Student Platform")

    if not smtp_user or not smtp_password:
        return False, "Gmail credentials not configured in .env."

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{smtp_user}>"
        message["To"] = to_email

        text_content = f"Hello,\n\nPlease click the link below to proceed:\n{link}\n\nAI Student Platform"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; margin: 0; padding: 30px; }}
            .card {{ max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); padding: 35px; color: #f8fafc; text-align: center; }}
            .btn {{ display: inline-block; background: #8b5cf6; color: #ffffff !important; padding: 14px 28px; border-radius: 12px; text-decoration: none; font-weight: 600; margin: 25px 0; }}
            .footer {{ font-size: 12px; color: #64748b; margin-top: 25px; }}
          </style>
        </head>
        <body>
          <div class="card">
            <h2 style="color: #8b5cf6; margin-top:0;">⚡ AI STUDENT PLATFORM</h2>
            <h3>{subject}</h3>
            <p style="color: #94a3b8;">Click the button below to verify your account or complete your request:</p>
            <a href="{link}" class="btn">Proceed & Verify</a>
            <p style="font-size: 12px; color: #64748b;">Or copy this link: <br><a href="{link}" style="color: #a78bfa;">{link}</a></p>
            <div class="footer">If you did not request this, please ignore this email.</div>
          </div>
        </body>
        </html>
        """

        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_server, smtp_port, timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], message.as_string())

        print(f"[Notifier] Verification link sent to {to_email}")
        return True, f"Verification link sent to {to_email}"
    except Exception as e:
        print(f"[Notifier] Email link sending failed: {e}")
        return False, str(e)
