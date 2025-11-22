"""add_extended_user_fields

Revision ID: 1da9ef061b12
Revises: 8a11fc5f9e2b
Create Date: 2025-11-22 23:25:56.796127

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1da9ef061b12"
down_revision: str | Sequence[str] | None = "8a11fc5f9e2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("username", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("is_bot", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "users", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default="false")
    )

    op.add_column("users", sa.Column("last_active_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users", sa.Column("total_interactions", sa.Integer(), nullable=False, server_default="0")
    )

    op.add_column(
        "users",
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("users", sa.Column("timezone", sa.String(64), nullable=True))

    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_last_active", "users", ["last_active_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_users_last_active", table_name="users")
    op.drop_index("idx_users_username", table_name="users")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "timezone")
    op.drop_column("users", "notifications_enabled")
    op.drop_column("users", "total_interactions")
    op.drop_column("users", "last_active_at")
    op.drop_column("users", "is_premium")
    op.drop_column("users", "is_bot")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "username")
