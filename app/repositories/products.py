from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PriceHistory
from app.db.models import Product as ProductModel

logger = logging.getLogger(__name__)

MAX_PRODUCTS_PER_USER = 20
PAGE_SIZE = 5


@dataclass
class Product:
    id: int
    user_id: int
    url: str
    title: str
    target_price: float
    current_price: float | None
    last_notified_price: float | None
    last_state: str | None
    is_active: bool


class ProductsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _to_dto(p: ProductModel) -> Product:
        return Product(
            id=p.id,
            user_id=p.user_id,
            url=p.url,
            title=p.title,
            target_price=float(p.target_price),
            current_price=float(p.current_price) if p.current_price is not None else None,
            last_notified_price=float(p.last_notified_price)
            if p.last_notified_price is not None
            else None,
            last_state=p.last_state,
            is_active=bool(p.is_active),
        )

    async def count_by_user(self, user_id: int) -> int:
        res = await self.session.execute(
            select(func.count()).select_from(ProductModel).where(ProductModel.user_id == user_id)
        )
        return int(res.scalar_one())

    async def list_page(
        self, user_id: int, page: int, page_size: int = PAGE_SIZE
    ) -> tuple[list[Product], int]:
        total = await self.count_by_user(user_id)
        pages = max((total + page_size - 1) // page_size, 1)
        page = max(1, min(page, pages))
        offset = (page - 1) * page_size

        res = await self.session.execute(
            select(ProductModel)
            .where(ProductModel.user_id == user_id)
            .order_by(ProductModel.id.desc())
            .limit(page_size)
            .offset(offset)
        )
        items = [self._to_dto(p) for p in res.scalars().all()]
        return items, pages

    async def get_by_url(self, user_id: int, url: str) -> Product | None:
        res = await self.session.execute(
            select(ProductModel).where(ProductModel.user_id == user_id, ProductModel.url == url)
        )
        p = res.scalar_one_or_none()
        return self._to_dto(p) if p else None

    async def get_by_id(self, product_id: int) -> Product | None:
        res = await self.session.execute(select(ProductModel).where(ProductModel.id == product_id))
        p = res.scalar_one_or_none()
        return self._to_dto(p) if p else None

    async def create(
        self,
        *,
        user_id: int,
        url: str,
        title: str,
        target_price: float,
        current_price: float | None,
    ) -> int:
        p = ProductModel(
            user_id=user_id,
            url=url,
            title=title,
            target_price=target_price,
            current_price=current_price,
        )
        self.session.add(p)
        try:
            await self.session.commit()
        except Exception as e:
            logger.warning(
                "Failed to create product, checking for duplicate | User: %d | URL: %s | Error: %s",
                user_id,
                url[:100],
                e,
            )
            await self.session.rollback()
            res = await self.session.execute(
                select(ProductModel.id).where(
                    ProductModel.user_id == user_id, ProductModel.url == url
                )
            )
            ex_id = res.scalar_one_or_none()
            if ex_id:
                logger.info("Found existing product ID: %d", ex_id)
            return int(ex_id) if ex_id is not None else 0
        await self.session.refresh(p)
        logger.debug("Product created | ID: %d | User: %d | Title: %s", p.id, user_id, title[:50])
        return int(p.id)

    async def add_price_history(self, product_id: int, price: float, source: str) -> None:
        ph = PriceHistory(product_id=product_id, price=price, source=source)
        self.session.add(ph)
        await self.session.commit()

    async def get_latest_price(self, product_id: int) -> tuple[float, str] | None:
        res = await self.session.execute(
            select(PriceHistory.price, PriceHistory.observed_at)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.observed_at.desc(), PriceHistory.id.desc())
            .limit(1)
        )
        row = res.first()
        if not row:
            return None
        price, observed_at = row
        return float(price), observed_at.isoformat()

    async def update_target_price(self, product_id: int, new_price: float) -> None:
        await self.session.execute(
            update(ProductModel).where(ProductModel.id == product_id).values(target_price=new_price)
        )
        await self.session.commit()

    async def list_all_active(self) -> AsyncGenerator[Product, None]:
        res = await self.session.stream_scalars(
            select(ProductModel).where(ProductModel.is_active.is_(True))
        )
        async for p in res:
            yield self._to_dto(p)

    async def update_current_and_history(
        self, product_id: int, price: float, source: str = "scheduler"
    ) -> None:
        try:
            await self.session.execute(
                update(ProductModel)
                .where(ProductModel.id == product_id)
                .values(current_price=price, updated_at=func.now())
            )
            self.session.add(PriceHistory(product_id=product_id, price=price, source=source))
            await self.session.commit()
        except Exception as e:
            logger.error(
                "Failed to update price for product %d: %s | Price: %.2f | Source: %s",
                product_id,
                e,
                price,
                source,
            )
            await self.session.rollback()
            raise

    async def set_last_state(
        self, product_id: int, state: str | None, last_notified_price: float | None
    ) -> None:
        await self.session.execute(
            update(ProductModel)
            .where(ProductModel.id == product_id)
            .values(
                last_state=state,
                last_notified_price=last_notified_price,
                updated_at=func.now(),
            )
        )
        await self.session.commit()

    async def delete(self, product_id: int) -> None:
        await self.session.execute(delete(ProductModel).where(ProductModel.id == product_id))
        await self.session.commit()
