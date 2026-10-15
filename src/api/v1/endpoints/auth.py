from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Response, status

from src.api.deps import CurrentUser, DbSession
from src.core.config import settings
from src.core.cookies import REFRESH_TOKEN_COOKIE, clear_auth_cookies, set_auth_cookies
from src.core.google import GoogleTokenError, GoogleUnavailableError, verify_google_id_token
from src.models import OtpPurpose
from src.schemas.auth import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ResetTokenResponse,
    VerifyEmailRequest,
    VerifyResetOtpRequest,
)
from src.schemas.common import MessageResponse
from src.schemas.invitation import AcceptInvitationRequest
from src.schemas.user import UserResponse
from src.services import auth_service, email_service, invitation_service, otp_service
from src.services.otp_service import OtpCooldownError

router = APIRouter(prefix="/auth", tags=["auth"])

RefreshTokenCookie = Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)]

EMAIL_ALREADY_VERIFIED = HTTPException(status.HTTP_409_CONFLICT, "Email is already verified")


@router.post("/login", response_model=UserResponse)
def login(data: LoginRequest, db: DbSession, response: Response):
    user = auth_service.authenticate(db, data.email, data.password)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/google", response_model=UserResponse)
def google_login(data: GoogleLoginRequest, db: DbSession, response: Response):
    try:
        identity = verify_google_id_token(data.id_token)
    except GoogleTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google ID token")
    except GoogleUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is unavailable")
    user = auth_service.login_with_google(db, identity)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/accept-invitation", response_model=UserResponse)
def accept_invitation(data: AcceptInvitationRequest, db: DbSession, response: Response):
    user = invitation_service.accept_invitation(db, data.token, data.password)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DbSession, response: Response):
    user = auth_service.register(db, data)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(db: DbSession, response: Response, refresh_token: RefreshTokenCookie = None) -> None:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    tokens = auth_service.rotate_refresh_token(db, refresh_token)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, response: Response, refresh_token: RefreshTokenCookie = None) -> None:
    if refresh_token:
        auth_service.revoke_refresh_token(db, refresh_token)
        db.commit()
    clear_auth_cookies(response)


@router.post("/email/send", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def send_email_verification(current_user: CurrentUser, db: DbSession, background_tasks: BackgroundTasks):
    if current_user.email_verified_at is not None:
        raise EMAIL_ALREADY_VERIFIED
    try:
        code = otp_service.create_otp(db, current_user, OtpPurpose.EMAIL_VERIFICATION)
    except OtpCooldownError as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Please wait {e.retry_after}s before requesting a new code",
            headers={"Retry-After": str(e.retry_after)},
        )
    db.commit()
    background_tasks.add_task(
        email_service.send_email_verification_otp, current_user.email, current_user.full_name, code
    )
    return MessageResponse(message="Verification code sent")


@router.post("/email/verify", response_model=UserResponse)
def verify_email(data: VerifyEmailRequest, current_user: CurrentUser, db: DbSession):
    if current_user.email_verified_at is not None:
        raise EMAIL_ALREADY_VERIFIED
    otp_service.consume_otp(db, current_user, OtpPurpose.EMAIL_VERIFICATION, data.otp)
    current_user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return current_user


@router.post("/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(data: ForgotPasswordRequest, db: DbSession, background_tasks: BackgroundTasks):
    # Same response whether or not the account exists, is disabled or is in cooldown
    user = auth_service.get_active_user_by_email(db, data.email)
    if user is not None:
        try:
            code = otp_service.create_otp(db, user, OtpPurpose.PASSWORD_RESET)
            db.commit()
            background_tasks.add_task(email_service.send_password_reset_otp, user.email, user.full_name, code)
        except OtpCooldownError:
            db.rollback()
    return MessageResponse(message="If the email is registered, a verification code has been sent")


@router.post("/verify", response_model=ResetTokenResponse)
def verify_reset_otp(data: VerifyResetOtpRequest, db: DbSession):
    user = auth_service.get_active_user_by_email(db, data.email)
    if user is None:
        raise otp_service.INVALID_OTP
    otp_service.consume_otp(db, user, OtpPurpose.PASSWORD_RESET, data.otp)
    reset_token = auth_service.create_password_reset_token(db, user)
    db.commit()
    return ResetTokenResponse(reset_token=reset_token, expires_in=settings.RESET_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: DbSession, response: Response):
    auth_service.reset_password(db, data.reset_token, data.new_password)
    db.commit()
    clear_auth_cookies(response)
    return MessageResponse(message="Password has been reset, please log in again")
