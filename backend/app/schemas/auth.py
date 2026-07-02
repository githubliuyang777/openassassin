from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    email: str = ""

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: str
    verification_token: str


class CaptchaGenerateResponse(BaseModel):
    captcha_token: str


class CaptchaVerifyRequest(BaseModel):
    captcha_token: str
    user_x: int = Field(ge=0, le=300)


class CaptchaVerifyResponse(BaseModel):
    success: bool
    verification_token: str | None = None
    message: str = ""


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str = Field(min_length=6)


class UpdateEmailRequest(BaseModel):
    email: str
