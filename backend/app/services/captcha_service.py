from __future__ import annotations

import random
import secrets
import threading
import time
from typing import Dict

CAPTCHA_TRACK_WIDTH = 300
CAPTCHA_TOLERANCE = 25
CAPTCHA_TTL = 300  # 5 minutes for captcha challenge
MAX_ATTEMPTS = 3
VERIFICATION_TOKEN_TTL = 120  # 2 minutes after solving

_lock = threading.Lock()
_captcha_store: dict[str, dict] = {}  # token -> {target_x, created_at, attempts}
_verification_store: dict[str, dict] = {}  # token -> {created_at}


def _cleanup_expired() -> None:
    now = time.time()
    expired_captcha = [t for t, v in _captcha_store.items() if now - v["created_at"] > CAPTCHA_TTL]
    for t in expired_captcha:
        del _captcha_store[t]
    expired_verify = [t for t, v in _verification_store.items() if now - v["created_at"] > VERIFICATION_TOKEN_TTL]
    for t in expired_verify:
        del _verification_store[t]


def generate_captcha() -> dict:
    """Generate a slider captcha challenge. Returns {captcha_token}."""
    token = secrets.token_urlsafe(32)
    target_x = random.randint(250, 275)
    with _lock:
        _cleanup_expired()
        _captcha_store[token] = {
            "target_x": target_x,
            "created_at": time.time(),
            "attempts": 0,
        }
    return {"captcha_token": token}


def verify_captcha(captcha_token: str, user_x: int) -> tuple[bool, str | None, str]:
    """Verify slider position. Returns (success, verification_token_or_None, message)."""
    with _lock:
        _cleanup_expired()
        entry = _captcha_store.get(captcha_token)
        if not entry:
            return False, None, "验证码已过期，请刷新重试"

        entry["attempts"] += 1
        attempts = entry["attempts"]

    if attempts > MAX_ATTEMPTS:
        with _lock:
            _captcha_store.pop(captcha_token, None)
        return False, None, "验证失败次数过多，请刷新重试"

    if abs(user_x - entry["target_x"]) <= CAPTCHA_TOLERANCE:
        verify_token = secrets.token_urlsafe(32)
        with _lock:
            _captcha_store.pop(captcha_token, None)
            _verification_store[verify_token] = {"created_at": time.time()}
        return True, verify_token, "验证通过"

    return False, None, f"验证未通过，还可尝试 {MAX_ATTEMPTS - attempts} 次"


def validate_verification_token(verification_token: str) -> bool:
    """Validate and consume a one-time verification token."""
    with _lock:
        _cleanup_expired()
        entry = _verification_store.pop(verification_token, None)
        if not entry:
            return False
        if time.time() - entry["created_at"] > VERIFICATION_TOKEN_TTL:
            return False
        return True
