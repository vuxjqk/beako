import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.security import generate_otp, hash_otp, verify_otp
from src.models import OtpCode, OtpPurpose, User

INVALID_OTP = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code")


class OtpCooldownError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Retry after {retry_after}s")
        self.retry_after = retry_after


def create_otp(db: Session, user: User, purpose: OtpPurpose) -> str:
    """Issue a new code, replacing any active one. Raises OtpCooldownError if called too soon."""
    now = datetime.now(timezone.utc)
    # Serialize concurrent requests for the same user so the cooldown can't be raced
    db.execute(select(User.id).where(User.id == user.id).with_for_update())

    last_created_at = db.scalar(
        select(OtpCode.created_at)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == purpose)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    if last_created_at is not None:
        elapsed = (now - last_created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            raise OtpCooldownError(math.ceil(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed))

    db.execute(
        update(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = generate_otp()
    db.add(
        OtpCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_otp(code, user_id=user.id, purpose=purpose.value),
            expires_at=now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
            created_at=now,
        )
    )
    return code


def consume_otp(db: Session, user: User, purpose: OtpPurpose, code: str) -> None:
    """Mark the active code as used, or raise INVALID_OTP (counting the failed attempt)."""
    now = datetime.now(timezone.utc)
    otp = db.scalar(
        select(OtpCode)
        .where(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
            OtpCode.expires_at > now,
            OtpCode.attempts < settings.OTP_MAX_ATTEMPTS,
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if otp is None:
        raise INVALID_OTP
    if not verify_otp(code, otp.code_hash, user_id=user.id, purpose=purpose.value):
        otp.attempts += 1
        db.commit()
        raise INVALID_OTP
    otp.consumed_at = now
