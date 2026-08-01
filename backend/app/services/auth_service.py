import random
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int, username: str, role: str, ver: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "ver": ver,  # token version; bumped on password change to revoke old tokens
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_mfa_token(user_id: int, username: str, ver: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "scope": "mfa_required",
        "ver": ver,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.totp_mfa_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_setup_token(user_id: int, username: str, enc_secret: str, ver: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "scope": "totp_setup",
        "enc_secret": enc_secret,
        "ver": ver,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.totp_setup_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_scoped_token(token: str, required_scope: str) -> dict:
    from jose import JWTError
    payload = decode_token(token)
    if payload.get("scope") != required_scope:
        raise JWTError(f"Token does not have required scope: {required_scope}")
    return payload


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_or_create_admin(db: Session) -> User:
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        user = User(
            username="admin",
            password_hash=hash_password(settings.admin_default_password),
            role="admin",
            email=settings.admin_email,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif settings.admin_email and not user.email:
        user.email = settings.admin_email
        db.commit()
        db.refresh(user)
    return user


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    user.token_version = (user.token_version or 0) + 1  # revoke all outstanding JWTs
    db.commit()
    return True


def generate_reset_code(db: Session, email: str) -> str:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return ""
    code = f"{random.randint(100000, 999999)}"
    user.reset_code = code
    user.reset_code_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    db.commit()
    return code


def reset_password_with_code(db: Session, email: str, code: str, new_password: str) -> bool:
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.reset_code:
        return False
    if user.reset_code != code:
        return False
    if user.reset_code_expires_at is None or datetime.now(timezone.utc).replace(tzinfo=None) > user.reset_code_expires_at:
        return False
    user.password_hash = hash_password(new_password)
    user.reset_code = None
    user.reset_code_expires_at = None
    user.token_version = (user.token_version or 0) + 1  # revoke all outstanding JWTs
    db.commit()
    return True
