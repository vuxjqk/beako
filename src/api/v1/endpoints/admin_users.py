import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from src.api.deps import DbSession, require_roles
from src.models import UserRole
from src.schemas.common import Page
from src.schemas.user import UpdateUserStatusRequest, UserResponse
from src.services import user_service

router = APIRouter(
    prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_roles(UserRole.ADMIN))]
)


@router.get("", response_model=Page[UserResponse])
def list_users(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 10,
    search: Annotated[str | None, Query(max_length=255, description="Matches full name or email")] = None,
    role: Annotated[Literal["user", "expert"] | None, Query()] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
):
    users, total, total_pages = user_service.list_users(
        db,
        page=page,
        page_size=page_size,
        search=search.strip() if search else None,
        role=UserRole(role) if role else None,
        is_active=is_active,
    )
    return Page[UserResponse](
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, db: DbSession):
    return user_service.get_manageable_user(db, user_id)


@router.patch("/{user_id}/status", response_model=UserResponse)
def update_user_status(user_id: uuid.UUID, data: UpdateUserStatusRequest, db: DbSession):
    user = user_service.set_user_active(db, user_id, data.is_active)
    db.commit()
    db.refresh(user)
    return user
