from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Lang = Literal["ru", "en"]


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    language: Mapped[Lang] = mapped_column(String(2), nullable=False, default="ru")
    created_at: Mapped[datetime] = mapped_column(
        default=None, server_default=text("CURRENT_TIMESTAMP")
    )

    products: Mapped[list[Product]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("language in ('ru','en')", name="users_language_ck"),)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    target_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    last_notified_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    last_state: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="products")
    history: Mapped[list[PriceHistory]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "url", name="uq_products_user_url"),
        Index("idx_products_user", "user_id"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(server_default=text("CURRENT_TIMESTAMP"))
    source: Mapped[str] = mapped_column(String(16), nullable=False)

    product: Mapped[Product] = relationship(back_populates="history")

    __table_args__ = (
        CheckConstraint("source in ('add','scheduler','manual')", name="price_history_source_ck"),
    )


Index(
    "idx_pricehist_product",
    PriceHistory.product_id,
    PriceHistory.observed_at.desc(),
)
