import smtplib
from email.mime.text import MIMEText

from app.config import settings


class EmailNotConfiguredError(Exception):
    pass


def _send_raw(to: str, subject: str, body: str) -> None:
    """Send an email via SMTP. Raises EmailNotConfiguredError if SMTP is not set up."""
    if not settings.smtp_host:
        raise EmailNotConfiguredError("邮件服务未配置，请联系管理员设置 SMTP 环境变量")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_username
    msg["To"] = to

    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    elif settings.smtp_use_tls:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        server.starttls()
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)

    try:
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(msg["From"], [to], msg.as_string())
    finally:
        server.quit()


def send_reset_code(email: str, code: str) -> None:
    body = f"""您的 Ops Platform 密码重置验证码为：

    {code}

该验证码 5 分钟内有效。如非本人操作，请忽略此邮件。
"""
    _send_raw(email, "Ops Platform 密码重置验证码", body)


def send_email(to: str, subject: str, body: str) -> None:
    """Public API for sending emails. Used by alert service."""
    _send_raw(to, subject, body)
