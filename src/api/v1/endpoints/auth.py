from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from src.api.deps import CurrentUser, DbSession
from src.core.cookies import REFRESH_TOKEN_COOKIE, clear_auth_cookies, set_auth_cookies
from src.schemas.auth import LoginRequest, RegisterRequest
from src.schemas.user import UserResponse
from src.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

RefreshTokenCookie = Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)]


@router.post("/login", response_model=UserResponse)
def login(data: LoginRequest, db: DbSession, response: Response):
    user = auth_service.authenticate(db, data.email, data.password)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DbSession, response: Response):
    user = auth_service.register(db, data)
    tokens = auth_service.issue_tokens(db, user)
    db.commit()
    db.refresh(user)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return user


@router.post("/refresh", status_code=status.HTTP_204_NO_CONTENT)
def refresh(db: DbSession, response: Response, refresh_token: RefreshTokenCookie = None) -> None:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    tokens = auth_service.rotate_refresh_token(db, refresh_token)
    db.commit()
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: DbSession, response: Response, refresh_token: RefreshTokenCookie = None) -> None:
    if refresh_token:
        auth_service.revoke_refresh_token(db, refresh_token)
        db.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser):
    return current_user
