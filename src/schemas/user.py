import uuid
from datetime import datetime

from pydantic import StrictBool

from src.models.user import UserRole
from src.schemas.base import CamelModel


class UpdateUserStatusRequest(CamelModel):
    is_active: StrictBool


class UserResponse(CamelModel):
    id: uuid.UUID
    full_name: str
    email: str
    email_verified_at: datetime | None
    avatar: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
