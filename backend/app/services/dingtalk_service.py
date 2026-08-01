import base64
import hashlib
import hmac
import time
import urllib.parse
import logging

import httpx
from sqlalchemy.orm import Session

from app.models.dingtalk import DingTalkConfig
from app.services.credential_service import encrypt, decrypt

logger = logging.getLogger(__name__)


class DingTalkNotConfiguredError(Exception):
    """Raised when DingTalk bot is not configured."""
    pass


def is_encrypted(value: str) -> bool:
    """Detect whether a stored value is an AES-GCM payload (nonce_hex:ct_hex)."""
    if not value or ":" not in value:
        return False
    nonce, ct = value.split(":", 1)
    try:
        return len(bytes.fromhex(nonce)) == 12 and len(bytes.fromhex(ct)) > 0
    except ValueError:
        return False


def _encrypt_secret(secret: str) -> str:
    """Encrypt a DingTalk webhook secret before storing. Idempotent."""
    if not secret or is_encrypted(secret):
        return secret
    return encrypt(secret)


def _decrypt_secret(secret: str) -> str:
    """Decrypt a stored secret; tolerate legacy plaintext values."""
    if not secret or not is_encrypted(secret):
        return secret
    return decrypt(secret)


def _build_sign(timestamp_ms: int, secret: str) -> str:
    """Build DingTalk HMAC-SHA256 signature."""
    string_to_sign = f"{timestamp_ms}\n{secret}"
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _get_signed_url(webhook_url: str, secret: str) -> str:
    """Append timestamp and sign to the webhook URL."""
    timestamp_ms = int(round(time.time() * 1000))
    sign = _build_sign(timestamp_ms, secret)
    sep = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{sep}timestamp={timestamp_ms}&sign={urllib.parse.quote(sign)}"


def get_config(db: Session) -> DingTalkConfig:
    """Get or create the singleton DingTalk configuration."""
    config = db.query(DingTalkConfig).filter(DingTalkConfig.id == 1).first()
    if config is None:
        config = DingTalkConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def get_status(db: Session) -> dict:
    """Return DingTalk connection status."""
    config = get_config(db)
    webhook_masked = None
    if config.webhook_url:
        # Mask the access_token in the URL
        url = config.webhook_url
        idx = url.find("access_token=")
        if idx != -1:
            token_start = idx + len("access_token=")
            token_end = url.find("&", token_start)
            if token_end == -1:
                token_end = len(url)
            webhook_masked = url[:token_start] + "****" + url[token_end:]
        else:
            webhook_masked = url[:40] + "****" if len(url) > 40 else url
    return {
        "configured": bool(config.webhook_url),
        "enabled": config.is_enabled,
        "webhook_masked": webhook_masked,
    }


def update_config(db: Session, webhook_url: str | None = None,
                  secret: str | None = None, is_enabled: bool | None = None) -> DingTalkConfig:
    """Update DingTalk configuration (webhook secret is encrypted at rest)."""
    config = get_config(db)
    if webhook_url is not None:
        config.webhook_url = webhook_url
    if secret is not None:
        config.secret = _encrypt_secret(secret)
    if is_enabled is not None:
        config.is_enabled = is_enabled
    db.commit()
    db.refresh(config)
    return config


def send_text(webhook_url: str, secret: str, content: str) -> dict:
    """Send a text message to a DingTalk group via webhook. Returns the DingTalk API response."""
    url = _get_signed_url(webhook_url, secret) if secret else webhook_url
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }
    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            errmsg = data.get("errmsg", "未知错误")
            raise Exception(f"钉钉返回错误 (errcode={data.get('errcode')}): {errmsg}")
        return data
    except httpx.HTTPStatusError as e:
        raise Exception(f"钉钉请求失败 (HTTP {e.response.status_code})") from e
    except httpx.RequestError as e:
        raise Exception(f"无法连接钉钉: {str(e)}") from e


def send_test_message(db: Session) -> dict:
    """Send a test message via the configured DingTalk bot."""
    config = get_config(db)
    if not config.webhook_url:
        raise DingTalkNotConfiguredError("钉钉未配置，请先在消息通知页面设置 Webhook 地址和密钥")
    content = "【告警】openAssassin 钉钉告警通知测试 — 连接成功！"
    # decrypt in memory only; never write the plaintext secret back to disk
    return send_text(config.webhook_url, _decrypt_secret(config.secret), content)


def send_alert(db: Session, at_mobiles: list[str] | None, title: str, body: str) -> None:
    """Send an alert message through DingTalk. Silently skips if not configured.

    Args:
        db: Database session.
        at_mobiles: List of mobile numbers to @-mention, or None for no @-mentions.
        title: Alert title (used as bold header in the message).
        body: Alert body text.
    """
    config = get_config(db)
    if not config.webhook_url or not config.is_enabled:
        return

    # Build DingTalk markdown message
    at_str = ""
    if at_mobiles:
        at_str = "\n> @" + " @".join(at_mobiles)

    content = f"【告警】{title}\n\n{body}{at_str}"

    try:
        send_text(config.webhook_url, _decrypt_secret(config.secret), content)
    except Exception as e:
        logger.warning("DingTalk alert delivery failed: %s", e)
