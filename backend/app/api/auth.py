from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.auth import (
    LoginRequest, TokenResponse, UserInfo,
    ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
    UpdateEmailRequest,
)
from app.services import auth_service
from app.services.email_service import send_reset_code, EmailNotConfiguredError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = auth_service.create_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserInfo)
def me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if db_user:
        return {"id": db_user.id, "username": db_user.username, "role": db_user.role, "email": db_user.email or ""}
    return user


@router.put("/password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ok = auth_service.change_password(db, user["id"], body.old_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码错误")
    return {"message": "密码修改成功，请重新登录"}


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    try:
        code = auth_service.generate_reset_code(db, body.email)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="验证码生成失败")

    if not code:
        # Don't reveal whether the email exists
        return {"message": "如该邮箱已注册，验证码已发送"}

    try:
        send_reset_code(body.email, code)
    except EmailNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="邮件服务未配置，请联系管理员设置 SMTP 环境变量 (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM)",
        )
    except Exception:
        auth_service.generate_reset_code.cache_clear if hasattr(auth_service.generate_reset_code, 'cache_clear') else None
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败，请检查 SMTP 配置")

    return {"message": "如该邮箱已注册，验证码已发送"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    ok = auth_service.reset_password_with_code(db, body.email, body.code, body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")
    return {"message": "密码重置成功"}


@router.put("/me/email")
def update_email(
    body: UpdateEmailRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db_user.email = body.email
    db.commit()
    return {"message": "邮箱更新成功", "email": body.email}

