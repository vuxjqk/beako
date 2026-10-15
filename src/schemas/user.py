import uuid
from datetime import datetime

from pydantic import Field, StrictBool, model_validator

from src.models.user import UserRole
from src.schemas.auth import FullName, Otp, Password
from src.schemas.base import CamelModel


class UpdateUserStatusRequest(CamelModel):
    is_active: StrictBool


class UpdateProfileRequest(CamelModel):
    full_name: FullName


class ChangePasswordRequest(CamelModel):
    current_password: str = Field(min_length=1)
    new_password: Password
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class DeleteAccountRequest(CamelModel):
    otp: Otp


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
