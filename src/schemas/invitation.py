from typing import Literal

from pydantic import Field, model_validator

from src.schemas.auth import FullName, NormalizedEmail, Password
from src.schemas.base import CamelModel


class InviteUserRequest(CamelModel):
    full_name: FullName
    email: NormalizedEmail
    # Admins can't be invited through this flow
    role: Literal["user", "expert"]


class AcceptInvitationRequest(CamelModel):
    token: str = Field(min_length=1)
    password: Password
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "AcceptInvitationRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
