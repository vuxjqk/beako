"""Transactional emails via Resend. Meant to run in a BackgroundTask so send latency never shows in API timing."""

import html
import logging

import resend

from src.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str, text_body: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set, email not sent\nTo: %s\nSubject: %s\n\n%s", to, subject, text_body)
        return
    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send(
            {"from": settings.MAIL_FROM, "to": [to], "subject": subject, "html": html_body, "text": text_body}
        )
    except Exception:
        logger.exception("Failed to send email to %s", to)


def _otp_email(full_name: str, intro: str, code: str) -> tuple[str, str]:
    minutes = settings.OTP_EXPIRE_MINUTES
    text_body = (
        f"Xin chào {full_name},\n\n"
        f"{intro}\n\n"
        f"Mã xác thực của bạn: {code}\n\n"
        f"Mã có hiệu lực trong {minutes} phút. Vui lòng không chia sẻ mã này với bất kỳ ai.\n"
        "Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua email.\n\n"
        "Beako"
    )
    html_body = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#1f2937">
  <p>Xin chào <strong>{html.escape(full_name)}</strong>,</p>
  <p>{html.escape(intro)}</p>
  <p style="font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;
            background:#f3f4f6;border-radius:8px;padding:16px 0;margin:24px 0">{code}</p>
  <p>Mã có hiệu lực trong <strong>{minutes} phút</strong>. Vui lòng không chia sẻ mã này với bất kỳ ai.</p>
  <p style="color:#6b7280;font-size:13px">Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua email.</p>
  <p>Beako</p>
</div>"""
    return html_body, text_body


ROLE_LABELS = {"user": "Người dùng", "expert": "Chuyên gia", "admin": "Quản trị viên"}


def send_invitation(to: str, full_name: str, role: str, link: str) -> None:
    hours = settings.INVITATION_EXPIRE_HOURS
    role_label = ROLE_LABELS.get(role, role)
    text_body = (
        f"Xin chào {full_name},\n\n"
        f"Bạn được mời tham gia Beako với vai trò {role_label}.\n"
        "Mở liên kết dưới đây để thiết lập mật khẩu và kích hoạt tài khoản:\n\n"
        f"{link}\n\n"
        f"Liên kết có hiệu lực trong {hours} giờ và chỉ dùng được một lần.\n"
        "Nếu bạn không mong đợi lời mời này, hãy bỏ qua email.\n\n"
        "Beako"
    )
    safe_link = html.escape(link, quote=True)
    html_body = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;max-width:480px;margin:0 auto;color:#1f2937">
  <p>Xin chào <strong>{html.escape(full_name)}</strong>,</p>
  <p>Bạn được mời tham gia Beako với vai trò <strong>{html.escape(role_label)}</strong>.</p>
  <p>Nhấn nút bên dưới để thiết lập mật khẩu và kích hoạt tài khoản:</p>
  <p style="text-align:center;margin:24px 0">
    <a href="{safe_link}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
       font-weight:bold;padding:12px 24px;border-radius:8px">Kích hoạt tài khoản</a>
  </p>
  <p style="font-size:13px;color:#6b7280">Hoặc sao chép liên kết này vào trình duyệt:<br>
    <a href="{safe_link}" style="color:#2563eb;word-break:break-all">{safe_link}</a></p>
  <p>Liên kết có hiệu lực trong <strong>{hours} giờ</strong> và chỉ dùng được một lần.</p>
  <p style="color:#6b7280;font-size:13px">Nếu bạn không mong đợi lời mời này, hãy bỏ qua email.</p>
  <p>Beako</p>
</div>"""
    send_email(to, "[Beako] Lời mời tham gia Beako", html_body, text_body)


def send_email_verification_otp(to: str, full_name: str, code: str) -> None:
    html_body, text_body = _otp_email(full_name, "Bạn đang xác thực địa chỉ email cho tài khoản Beako.", code)
    send_email(to, "[Beako] Mã xác thực email", html_body, text_body)


def send_password_reset_otp(to: str, full_name: str, code: str) -> None:
    html_body, text_body = _otp_email(full_name, "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản Beako của bạn.", code)
    send_email(to, "[Beako] Mã đặt lại mật khẩu", html_body, text_body)
