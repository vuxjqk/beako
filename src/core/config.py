from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    COOKIE_SECURE: bool = False

    OTP_SECRET_KEY: str
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_ATTEMPTS: int = 5
    RESET_TOKEN_EXPIRE_MINUTES: int = 15
    INVITATION_EXPIRE_HOURS: int = 72
    INVITATION_RESEND_COOLDOWN_SECONDS: int = 60

    FRONTEND_URL: str = "http://localhost:3000"

    RESEND_API_KEY: str = ""
    MAIL_FROM: str = "Beako <onboarding@resend.dev>"

    GOOGLE_CLIENT_ID: str = ""

    @property
    def google_client_ids(self) -> list[str]:
        return [cid.strip() for cid in self.GOOGLE_CLIENT_ID.split(",") if cid.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
