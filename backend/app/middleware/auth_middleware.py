from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import decode_token, decode_scoped_token

bearer_scheme = HTTPBearer()


def _check_token_version(payload: dict) -> dict:
    """Ensure the JWT's ver claim matches the user's current token_version.

    token_version is bumped on password change/reset, which invalidates all
    previously issued tokens (no-JWT-revocation fix).
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        if payload.get("ver", 0) != (user.token_version or 0):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked, please log in again",
            )
        return {"id": user.id, "username": user.username, "role": user.role, "_user": user}
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return _check_token_version(payload)


def get_current_user_from_mfa_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_scoped_token(credentials.credentials, "mfa_required")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA token")
    return _check_token_version(payload)


def get_current_user_from_setup_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_scoped_token(credentials.credentials, "totp_setup")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid setup token")
    result = _check_token_version(payload)
    result["enc_secret"] = payload["enc_secret"]
    return result
