from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile, status

from src.api.deps import CurrentUser, DbSession
from src.core.cookies import clear_auth_cookies, set_auth_cookies
from src.models import OtpPurpose
from src.schemas.common import MessageResponse
from src.schemas.user import ChangePasswordRequest, DeleteAccountRequest, UpdateProfileRequest, UserResponse
from src.services import account_service, auth_service, avatar_service, email_service, otp_service
from src.services.otp_service import OtpCooldownError

router = APIRouter(prefix="/auth/me", tags=["me"])


@router.get("", response_model=UserResponse)
def me(current_user: CurrentUser):
    return current_user


@router.patch("", response_model=UserResponse)
def update_profile(data: UpdateProfileRequest, current_user: CurrentUser, db: DbSession):
    current_user.full_name = data.full_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/password", response_model=MessageResponse)
def change_password(data: ChangePasswordRequest, current_user: CurrentUser, db: DbSession, response: Response):
    account_service.change_password(db, current_user, data.current_password, data.new_password)
    # Every other device is signed out; keep this one signed in with fresh tokens
    tokens = auth_service.issue_tokens(db, current_user)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return MessageResponse(message="Password changed, other devices have been signed out")


@router.post("/delete-otp", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def send_delete_account_otp(current_user: CurrentUser, db: DbSession, background_tasks: BackgroundTasks):
    try:
        code = otp_service.create_otp(db, current_user, OtpPurpose.ACCOUNT_DELETION)
    except OtpCooldownError as e:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Please wait {e.retry_after}s before requesting a new code",
            headers={"Retry-After": str(e.retry_after)},
        )
    db.commit()
    background_tasks.add_task(
        email_service.send_account_deletion_otp, current_user.email, current_user.full_name, code
    )
    return MessageResponse(message="Verification code sent")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(data: DeleteAccountRequest, current_user: CurrentUser, db: DbSession, response: Response) -> None:
    account_service.delete_account(db, current_user, data.otp)
    db.commit()
    clear_auth_cookies(response)


@router.put("/avatar", response_model=UserResponse)
def upload_avatar(
    current_user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(description="JPEG, PNG or WebP, max 2 MB")],
):
    return avatar_service.update_avatar(db, current_user, file)


@router.delete("/avatar", response_model=UserResponse)
def delete_avatar(current_user: CurrentUser, db: DbSession):
    return avatar_service.remove_avatar(db, current_user)
