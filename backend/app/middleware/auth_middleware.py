from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.user import User
from app.services.auth_service import decode_token, decode_scoped_token

bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {"id": int(payload["sub"]), "username": payload["username"], "role": payload["role"]}


def get_current_admin_user(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Require the current user to still exist in DB and have the admin role."""
    db_user = db.get(User, user["id"])
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if db_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return {"id": db_user.id, "username": db_user.username, "role": db_user.role}


def get_current_user_from_mfa_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_scoped_token(credentials.credentials, "mfa_required")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA token")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return {"id": user.id, "username": user.username, "role": user.role, "_user": user}
    finally:
        db.close()


def get_current_user_from_setup_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_scoped_token(credentials.credentials, "totp_setup")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid setup token")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return {"id": user.id, "username": user.username, "enc_secret": payload["enc_secret"], "_user": user}
    finally:
        db.close()
