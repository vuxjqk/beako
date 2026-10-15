import math
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.security import generate_secure_token, hash_password, hash_token
from src.models import InvitationToken, User, UserRole
from src.schemas.invitation import InviteUserRequest
from src.services.auth_service import EMAIL_TAKEN

INVALID_INVITATION = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired invitation")
INVITATION_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "No invitation found for this user")


def build_invitation_link(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/accept-invitation?{urlencode({'token': token})}"


def invite_user(db: Session, data: InviteUserRequest, invited_by: User) -> tuple[User, str]:
    """Create a pending account (no password, unverified) and return it with the raw invitation token."""
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise EMAIL_TAKEN
    user = User(full_name=data.full_name, email=data.email, role=UserRole(data.role))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise EMAIL_TAKEN

    return user, _create_invitation_token(db, user, invited_by, datetime.now(timezone.utc))


def resend_invitation(db: Session, user_id: uuid.UUID, invited_by: User) -> tuple[User, str]:
    """Replace any unused invitation of a still-pending user with a fresh one."""
    now = datetime.now(timezone.utc)
    user = db.get(User, user_id, with_for_update=True)
    if user is None or user.deleted_at is not None:
        raise INVITATION_NOT_FOUND
    last_sent_at = db.scalar(
        select(InvitationToken.created_at)
        .where(InvitationToken.user_id == user.id)
        .order_by(InvitationToken.created_at.desc())
        .limit(1)
    )
    if last_sent_at is None:
        raise INVITATION_NOT_FOUND
    # Activated by accepting, or by proving the inbox another way (Google, password reset)
    if user.password_hash is not None or user.email_verified_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation has already been accepted")
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account is disabled")

    elapsed = (now - last_sent_at).total_seconds()
    if elapsed < settings.INVITATION_RESEND_COOLDOWN_SECONDS:
        retry_after = math.ceil(settings.INVITATION_RESEND_COOLDOWN_SECONDS - elapsed)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Please wait {retry_after}s before resending the invitation",
            headers={"Retry-After": str(retry_after)},
        )

    _invalidate_invitation_tokens(db, user.id, now)
    return user, _create_invitation_token(db, user, invited_by, now)


def _create_invitation_token(db: Session, user: User, invited_by: User, now: datetime) -> str:
    token = generate_secure_token()
    db.add(
        InvitationToken(
            user_id=user.id,
            invited_by_id=invited_by.id,
            token_hash=hash_token(token),
            expires_at=now + timedelta(hours=settings.INVITATION_EXPIRE_HOURS),
            created_at=now,
        )
    )
    return token


def _invalidate_invitation_tokens(db: Session, user_id: uuid.UUID, now: datetime) -> None:
    db.execute(
        update(InvitationToken)
        .where(InvitationToken.user_id == user_id, InvitationToken.used_at.is_(None))
        .values(used_at=now)
    )


def accept_invitation(db: Session, token: str, password: str) -> User:
    now = datetime.now(timezone.utc)
    invitation = db.scalar(
        select(InvitationToken).where(InvitationToken.token_hash == hash_token(token)).with_for_update()
    )
    if invitation is None or invitation.used_at is not None or invitation.expires_at <= now:
        raise INVALID_INVITATION
    user = db.get(User, invitation.user_id)
    if user is None or not user.can_authenticate:
        raise INVALID_INVITATION

    user.password_hash = hash_password(password)
    # The token arrived by email, which proves ownership of the inbox
    if user.email_verified_at is None:
        user.email_verified_at = now
    _invalidate_invitation_tokens(db, user.id, now)
    return user
