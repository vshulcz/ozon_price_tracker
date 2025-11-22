"""Initial schema

Revision ID: 8a11fc5f9e2b
Revises:
Create Date: 2025-11-21 16:06:23.872957

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a11fc5f9e2b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("language", sa.String(length=2), nullable=False, server_default="ru"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("language in ('ru','en')", name="users_language_ck"),
    )

    # Create products table
    op.create_table(
        "products",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("target_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("last_notified_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("last_state", sa.String(length=16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "url", name="uq_products_user_url"),
    )
    op.create_index("idx_products_user", "products", ["user_id"])

    # Create price_history table
    op.create_table(
        "price_history",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "product_id",
            sa.BigInteger(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "source in ('add','scheduler','manual')", name="price_history_source_ck"
        ),
    )
    op.create_index(
        "idx_pricehist_product", "price_history", ["product_id", sa.text("observed_at DESC")]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_pricehist_product", table_name="price_history")
    op.drop_table("price_history")
    op.drop_index("idx_products_user", table_name="products")
    op.drop_table("products")
    op.drop_table("users")
