import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import (
    get_current_user,
    get_current_user_from_mfa_token,
    get_current_user_from_setup_token,
)
from app.middleware.audit_middleware import _get_client_ip
from app.schemas.auth import (
    LoginRequest, TokenResponse, UserInfo,
    ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest,
    UpdateEmailRequest,
    CaptchaGenerateResponse, CaptchaVerifyRequest, CaptchaVerifyResponse,
    MfaRequiredResponse, MfaVerifyRequest, MfaRecoveryRequest,
    MfaStatusResponse, MfaSetupVerifyEmailRequest,
    MfaSetupVerifyEmailResponse, MfaSetupConfirmRequest,
    MfaSetupConfirmResponse, MfaDisableRequest,
)
from app.services import captcha_service
from app.services import auth_service
from app.services.email_service import send_reset_code, send_email, EmailNotConfiguredError
from app.services import totp_service
from app.services.credential_service import encrypt, decrypt

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse | MfaRequiredResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    try:
        from app.services.audit_service import create_log
        create_log(db, user_id=user.id, username=user.username,
                   action="POST", resource="/api/v1/auth/login",
                   resource_type="认证", detail="用户登录",
                   ip_address=_get_client_ip(request),
                   user_agent=request.headers.get("User-Agent", ""))
    except Exception:
        pass

    if user.totp_enabled:
        mfa_token = auth_service.create_mfa_token(user.id, user.username)
        return MfaRequiredResponse(mfa_token=mfa_token)

    token = auth_service.create_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(request: Request, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        from app.services.audit_service import create_log
        create_log(db, user_id=user["id"], username=user["username"],
                   action="POST", resource="/api/v1/auth/logout",
                   resource_type="认证", detail="用户登出",
                   ip_address=_get_client_ip(request),
                   user_agent=request.headers.get("User-Agent", ""))
    except Exception:
        pass
    return {"message": "已登出"}


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


@router.post("/captcha/generate", response_model=CaptchaGenerateResponse)
def generate_captcha():
    """Generate a slider captcha challenge. No authentication required."""
    result = captcha_service.generate_captcha()
    return CaptchaGenerateResponse(**result)


@router.post("/captcha/verify", response_model=CaptchaVerifyResponse)
def verify_captcha(body: CaptchaVerifyRequest):
    """Verify slider captcha position. Returns a one-time verification_token on success."""
    ok, token, msg = captcha_service.verify_captcha(body.captcha_token, body.user_x)
    return CaptchaVerifyResponse(success=ok, verification_token=token, message=msg)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    if not captcha_service.validate_verification_token(body.verification_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="人机验证失败或已过期，请重新验证",
        )

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


# ── MFA / TOTP ──

def _audit(db, user_id, username, action, detail, request):
    try:
        from app.services.audit_service import create_log
        create_log(db, user_id=user_id, username=username,
                   action=action, resource=f"/api/v1/auth{action.lower()}",
                   resource_type="认证", detail=detail,
                   ip_address=_get_client_ip(request),
                   user_agent=request.headers.get("User-Agent", ""))
    except Exception:
        pass


@router.post("/mfa/verify", response_model=TokenResponse)
def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    mfa_user: dict = Depends(get_current_user_from_mfa_token),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    user = db.query(User).filter(User.id == mfa_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    totp_service.check_rate_limit(user)

    encrypted_secret = user.totp_secret
    if not encrypted_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP未配置")

    secret = decrypt(encrypted_secret)
    if totp_service.verify_totp(secret, body.totp_code):
        totp_service.reset_failed_attempts(user)
        db.commit()
        token = auth_service.create_token(user.id, user.username, user.role)
        _audit(db, user.id, user.username, "POST", "MFA验证成功", request)
        return TokenResponse(access_token=token)

    totp_service.record_failed_attempt(user)
    db.commit()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOTP验证码错误")


@router.post("/mfa/recovery", response_model=TokenResponse)
def mfa_recovery(
    body: MfaRecoveryRequest,
    request: Request,
    mfa_user: dict = Depends(get_current_user_from_mfa_token),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    user = db.query(User).filter(User.id == mfa_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if totp_service.verify_backup_code(user, body.recovery_code):
        totp_service.reset_failed_attempts(user)
        db.commit()
        token = auth_service.create_token(user.id, user.username, user.role)
        _audit(db, user.id, user.username, "POST", "备用码验证成功", request)
        return TokenResponse(access_token=token)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="备用码无效或已被使用")


@router.get("/mfa/status", response_model=MfaStatusResponse)
def mfa_status(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    remaining = 0
    if db_user.backup_codes:
        remaining = len(json.loads(db_user.backup_codes))

    return MfaStatusResponse(
        totp_enabled=bool(db_user.totp_enabled),
        backup_codes_remaining=remaining,
    )


@router.post("/mfa/setup/init")
def mfa_setup_init(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if not db_user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先设置邮箱后再绑定TOTP")

    code = totp_service.generate_email_otp()
    db_user.totp_email_code = code
    db_user.totp_email_code_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)
    db.commit()

    try:
        send_email(db_user.email, "openAssassin TOTP绑定验证码",
                   f"您的TOTP绑定验证码为：{code}，5分钟内有效。如非本人操作，请忽略此邮件。")
    except EmailNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="邮件服务未配置",
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="邮件发送失败")

    return {"message": "验证码已发送至您的邮箱"}


@router.post("/mfa/setup/verify-email", response_model=MfaSetupVerifyEmailResponse)
def mfa_setup_verify_email(
    body: MfaSetupVerifyEmailRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if not db_user.totp_email_code or db_user.totp_email_code != body.email_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    if db_user.totp_email_code_expires_at is None or \
       datetime.now(timezone.utc).replace(tzinfo=None) > db_user.totp_email_code_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码已过期")

    secret = totp_service.generate_secret()
    uri = totp_service.get_provisioning_uri(secret, db_user.username, settings.totp_issuer)
    enc_secret = encrypt(secret)
    setup_token = auth_service.create_setup_token(db_user.id, db_user.username, enc_secret)

    db_user.totp_email_code = None
    db_user.totp_email_code_expires_at = None
    db.commit()

    return MfaSetupVerifyEmailResponse(provisioning_uri=uri, setup_token=setup_token)


@router.post("/mfa/setup/confirm", response_model=MfaSetupConfirmResponse)
def mfa_setup_confirm(
    body: MfaSetupConfirmRequest,
    request: Request,
    setup_user: dict = Depends(get_current_user_from_setup_token),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    user = db.query(User).filter(User.id == setup_user["id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    enc_secret = setup_user["enc_secret"]
    secret = decrypt(enc_secret)

    if not totp_service.verify_totp(secret, body.totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOTP验证码错误")

    backup_codes = totp_service.generate_backup_codes()
    hashed = totp_service.hash_backup_codes(backup_codes)

    user.totp_secret = encrypt(secret)
    user.totp_enabled = 1
    user.backup_codes = hashed
    user.backup_codes_used = 0
    db.commit()

    _audit(db, user.id, user.username, "POST", "TOTP绑定成功", request)

    return MfaSetupConfirmResponse(backup_codes=backup_codes)


@router.post("/mfa/disable")
def mfa_disable(
    body: MfaDisableRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.user import User
    db_user = db.query(User).filter(User.id == user["id"]).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if not auth_service.verify_password(body.password, db_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")

    db_user.totp_secret = None
    db_user.totp_enabled = 0
    db_user.totp_email_code = None
    db_user.totp_email_code_expires_at = None
    db_user.totp_failed_attempts = 0
    db_user.totp_failed_at = None
    db_user.backup_codes = None
    db_user.backup_codes_used = 0
    db.commit()

    _audit(db, db_user.id, db_user.username, "POST", "TOTP已禁用", request)

    return {"message": "TOTP已禁用"}

