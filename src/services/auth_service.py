from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_dummy_password,
    verify_password,
)
from src.models import PasswordResetToken, RefreshToken, User
from src.schemas.auth import RegisterRequest


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


INVALID_CREDENTIALS = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
INVALID_REFRESH_TOKEN = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
EMAIL_TAKEN = HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
INVALID_RESET_TOKEN = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")


def get_active_user_by_email(db: Session, email: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    return user if user is not None and user.can_authenticate else None


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.password_hash is None:
        verify_dummy_password(password)
        raise INVALID_CREDENTIALS
    if not verify_password(password, user.password_hash):
        raise INVALID_CREDENTIALS
    # Only reveal account state after the password is proven correct
    if user.deleted_at is not None:
        raise INVALID_CREDENTIALS
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return user


def register(db: Session, data: RegisterRequest) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise EMAIL_TAKEN
    user = User(full_name=data.full_name, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise EMAIL_TAKEN
    return user


def issue_tokens(db: Session, user: User) -> TokenPair:
    refresh_token = generate_secure_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return TokenPair(access_token=create_access_token(user.id), refresh_token=refresh_token)


def rotate_refresh_token(db: Session, refresh_token: str) -> TokenPair:
    now = datetime.now(timezone.utc)
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token)).with_for_update()
    )
    if token is None:
        raise INVALID_REFRESH_TOKEN
    if token.revoked_at is not None:
        # A rotated token was replayed: assume it was stolen and end every session of this user
        _revoke_all_user_tokens(db, token.user_id, now)
        db.commit()
        raise INVALID_REFRESH_TOKEN
    if token.expires_at <= now:
        raise INVALID_REFRESH_TOKEN

    user = db.get(User, token.user_id)
    if user is None or not user.can_authenticate:
        raise INVALID_REFRESH_TOKEN

    token.revoked_at = now
    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def create_password_reset_token(db: Session, user: User) -> str:
    now = datetime.now(timezone.utc)
    _invalidate_reset_tokens(db, user.id, now)
    reset_token = generate_secure_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(reset_token),
            expires_at=now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    return reset_token


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    now = datetime.now(timezone.utc)
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(reset_token))
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise INVALID_RESET_TOKEN
    user = db.get(User, token.user_id)
    if user is None or not user.can_authenticate:
        raise INVALID_RESET_TOKEN

    token.used_at = now
    _invalidate_reset_tokens(db, user.id, now)
    user.password_hash = hash_password(new_password)
    # Receiving the OTP proved ownership of the inbox
    if user.email_verified_at is None:
        user.email_verified_at = now
    _revoke_all_user_tokens(db, user.id, now)


def _invalidate_reset_tokens(db: Session, user_id, now: datetime) -> None:
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )


def _revoke_all_user_tokens(db: Session, user_id, now: datetime) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
