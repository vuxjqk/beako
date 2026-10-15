from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field, StringConstraints, field_validator, model_validator

from src.schemas.base import CamelModel

NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.lower())]


class LoginRequest(CamelModel):
    email: NormalizedEmail
    password: str = Field(min_length=1)


class RegisterRequest(CamelModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    email: NormalizedEmail
    password: str = Field(min_length=8)
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        # bcrypt only uses the first 72 bytes
        if len(v.encode()) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
