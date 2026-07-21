"""Self-service profile picture — users.avatar_key.

Adds a nullable object-storage key that points at the user's uploaded avatar
inside the ``avatars`` bucket. NULL means "no upload" and the frontend renders
the generated initial/gradient avatar instead.

Revision ID: 0009_user_avatar
Revises: 0008_incidents_admin_mgmt
Create Date: 2026-07-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_user_avatar"
down_revision: Union[str, None] = "0008_incidents_admin_mgmt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
