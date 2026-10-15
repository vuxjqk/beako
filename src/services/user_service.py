import math
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.models import User, UserRole
from src.services.auth_service import revoke_all_user_tokens

# Same response for admins as for missing ids, so admin ids can't be probed
USER_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "User not found")


def _manageable_users() -> Select[tuple[User]]:
    """Users an admin can see and manage: never admins, never soft-deleted."""
    return select(User).where(User.role != UserRole.ADMIN, User.deleted_at.is_(None))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_manageable_user(db: Session, user_id: uuid.UUID, *, for_update: bool = False) -> User:
    stmt = _manageable_users().where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    user = db.scalar(stmt)
    if user is None:
        raise USER_NOT_FOUND
    return user


def list_users(
    db: Session,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[Sequence[User], int, int]:
    """Return (users, total, total_pages)."""
    stmt = _manageable_users()
    if search:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            or_(User.full_name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\"))
        )
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(
        stmt.order_by(User.created_at.desc(), User.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return users, total, math.ceil(total / page_size)


def set_user_active(db: Session, user_id: uuid.UUID, is_active: bool) -> User:
    user = get_manageable_user(db, user_id, for_update=True)
    user.is_active = is_active
    if not is_active:
        # Access tokens are rejected immediately too: get_current_user checks is_active on every request
        revoke_all_user_tokens(db, user.id, datetime.now(timezone.utc))
    return user
