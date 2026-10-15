from fastapi import Response

from src.core.config import settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
# Browser only sends the refresh token to auth endpoints
REFRESH_TOKEN_COOKIE_PATH = "/api/v1/auth"

_COOKIE_OPTIONS = {"httponly": True, "samesite": "lax", "secure": settings.COOKIE_SECURE}


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **_COOKIE_OPTIONS,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_TOKEN_COOKIE_PATH,
        **_COOKIE_OPTIONS,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", **_COOKIE_OPTIONS)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=REFRESH_TOKEN_COOKIE_PATH, **_COOKIE_OPTIONS)
