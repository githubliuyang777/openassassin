import smtplib
from email.mime.text import MIMEText

from app.config import settings


class EmailNotConfiguredError(Exception):
    pass


def send_reset_code(email: str, code: str) -> None:
    if not settings.smtp_host:
        raise EmailNotConfiguredError("邮件服务未配置，请联系管理员设置 SMTP 环境变量")

    body = f"""您的 Ops Platform 密码重置验证码为：

    {code}

该验证码 5 分钟内有效。如非本人操作，请忽略此邮件。
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "Ops Platform 密码重置验证码"
    msg["From"] = settings.smtp_from or settings.smtp_username
    msg["To"] = email

    if settings.smtp_use_tls:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)

    try:
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(msg["From"], [email], msg.as_string())
    finally:
        server.quit()
