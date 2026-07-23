"""Google Sign-In — users.google_sub, users.auth_provider, nullable password_hash.

Adds a nullable, unique google_sub column (Google's stable per-account "sub"
claim) and an auth_provider marker ('local' | 'google'). password_hash becomes
nullable because accounts created via Google Sign-In may never set a password.

Revision ID: 0010_google_auth
Revises: 0009_user_avatar
Create Date: 2026-07-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_google_auth"
down_revision: Union[str, None] = "0009_user_avatar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(16), nullable=False, server_default="local"),
    )
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)
    op.drop_column("users", "auth_provider")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
