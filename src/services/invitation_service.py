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

    token = generate_secure_token()
    db.add(
        InvitationToken(
            user_id=user.id,
            invited_by_id=invited_by.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.INVITATION_EXPIRE_HOURS),
        )
    )
    return user, token


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
    db.execute(
        update(InvitationToken)
        .where(InvitationToken.user_id == user.id, InvitationToken.used_at.is_(None))
        .values(used_at=now)
    )
    return user
