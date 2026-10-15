from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field, StringConstraints, model_validator

from src.core.config import settings
from src.schemas.base import CamelModel


def _fits_bcrypt(v: str) -> str:
    # bcrypt only uses the first 72 bytes
    if len(v.encode()) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return v


NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]
Password = Annotated[str, Field(min_length=8), AfterValidator(_fits_bcrypt)]
Otp = Annotated[str, StringConstraints(pattern=rf"^\d{{{settings.OTP_LENGTH}}}$")]


class LoginRequest(CamelModel):
    email: NormalizedEmail
    password: str = Field(min_length=1)


class GoogleLoginRequest(CamelModel):
    id_token: str = Field(min_length=1)


class RegisterRequest(CamelModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    email: NormalizedEmail
    password: Password
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class VerifyEmailRequest(CamelModel):
    otp: Otp


class ForgotPasswordRequest(CamelModel):
    email: NormalizedEmail


class VerifyResetOtpRequest(CamelModel):
    email: NormalizedEmail
    otp: Otp


class ResetTokenResponse(CamelModel):
    reset_token: str
    expires_in: int


class ResetPasswordRequest(CamelModel):
    reset_token: str = Field(min_length=1)
    new_password: Password
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
