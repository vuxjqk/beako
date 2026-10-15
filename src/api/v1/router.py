from fastapi import APIRouter

from src.api.v1.endpoints import admin, admin_users, auth

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(admin_users.router)
