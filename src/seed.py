"""Seed default accounts. Run: python -m src.seed"""

from datetime import datetime, timezone

from sqlalchemy import select

from src.core.security import hash_password
from src.models import SessionLocal, User, UserRole

DEFAULT_PASSWORD = "12345678"

SEED_USERS = [
    {"full_name": "Admin", "email": "admin@beako.com", "role": UserRole.ADMIN},
    {"full_name": "Expert", "email": "expert@beako.com", "role": UserRole.EXPERT},
    {"full_name": "User", "email": "user@beako.com", "role": UserRole.USER},
]


def seed_users() -> None:
    with SessionLocal() as db:
        for data in SEED_USERS:
            if db.scalar(select(User).where(User.email == data["email"])):
                print(f"skip    {data['email']} (already exists)")
                continue
            db.add(
                User(
                    **data,
                    email_verified_at=datetime.now(timezone.utc),
                    password_hash=hash_password(DEFAULT_PASSWORD),
                )
            )
            print(f"created {data['email']}")
        db.commit()


if __name__ == "__main__":
    seed_users()
