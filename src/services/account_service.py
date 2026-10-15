from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import hash_password, verify_password
from src.models import OtpPurpose, User
from src.services import otp_service
from src.services.auth_service import revoke_all_user_tokens


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """Set a new password and revoke every session; the caller issues fresh tokens for this device."""
    if user.password_hash is None:
        # Google-only or not-yet-activated account: there is no current password to check
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Account has no password yet, use forgot password to set one"
        )
    # 400 rather than 401 so clients don't treat it as an expired session
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if verify_password(new_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different from the current one")

    user.password_hash = hash_password(new_password)
    revoke_all_user_tokens(db, user.id, datetime.now(timezone.utc))


def delete_account(db: Session, user: User, otp: str) -> None:
    """Soft delete: keep the row, set deleted_at and end every session."""
    otp_service.consume_otp(db, user, OtpPurpose.ACCOUNT_DELETION, otp)
    now = datetime.now(timezone.utc)
    user.deleted_at = now
    revoke_all_user_tokens(db, user.id, now)
