"""add account_deletion otp purpose

Revision ID: 95d6a7b2110e
Revises: 0eeff29fe124
Create Date: 2026-10-15 16:56:42.921850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95d6a7b2110e'
down_revision: Union[str, None] = '0eeff29fe124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate doesn't detect new enum values
    op.execute("ALTER TYPE otp_purpose ADD VALUE IF NOT EXISTS 'account_deletion'")


def downgrade() -> None:
    # Postgres can't drop an enum value: rebuild the type without it
    op.execute("DELETE FROM otp_codes WHERE purpose = 'account_deletion'")
    op.execute("ALTER TYPE otp_purpose RENAME TO otp_purpose_old")
    op.execute("CREATE TYPE otp_purpose AS ENUM ('email_verification', 'password_reset')")
    op.execute(
        "ALTER TABLE otp_codes ALTER COLUMN purpose TYPE otp_purpose USING purpose::text::otp_purpose"
    )
    op.execute("DROP TYPE otp_purpose_old")
