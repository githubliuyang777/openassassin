import json
import random
import string
from datetime import datetime, timezone, timedelta

import pyotp
from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.services.credential_service import encrypt, decrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, username: str, issuer: str = "openAssassin") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_email_otp() -> str:
    return str(random.randint(100000, 999999))


def generate_backup_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        code = f"{chars[0:4]}-{chars[4:8]}-{chars[8:10]}"
        codes.append(code)
    return codes


def hash_backup_codes(codes: list[str]) -> str:
    return json.dumps([pwd_context.hash(c) for c in codes])


def verify_backup_code(user, code: str) -> bool:
    if not user.backup_codes:
        return False
    stored = json.loads(user.backup_codes)
    for i, h in enumerate(stored):
        if pwd_context.verify(code, h):
            stored.pop(i)
            user.backup_codes = json.dumps(stored) if stored else None
            user.backup_codes_used = (user.backup_codes_used or 0) + 1
            return True
    return False


def check_rate_limit(user) -> None:
    max_attempts = 5
    window_minutes = 5
    if (user.totp_failed_attempts or 0) >= max_attempts:
        if user.totp_failed_at:
            elapsed = (datetime.now(timezone.utc) - user.totp_failed_at.replace(tzinfo=timezone.utc)).total_seconds()
            if elapsed < window_minutes * 60:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail=f"TOTP 验证失败次数过多，请 {int(window_minutes - elapsed / 60)} 分钟后重试")
            user.totp_failed_attempts = 0
            user.totp_failed_at = None


def record_failed_attempt(user) -> None:
    user.totp_failed_attempts = (user.totp_failed_attempts or 0) + 1
    user.totp_failed_at = datetime.now(timezone.utc)


def reset_failed_attempts(user) -> None:
    user.totp_failed_attempts = 0
    user.totp_failed_at = None
