from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from src.schemas.auth import NormalizedEmail, Password
from src.schemas.base import CamelModel


class InviteUserRequest(CamelModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
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
