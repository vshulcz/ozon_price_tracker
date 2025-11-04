import pytest

from app.repositories.products import PAGE_SIZE
from app.repositories.users import PostgresUserRepo


@pytest.mark.asyncio
async def test_user_repo_ensure_and_language(users_repo: PostgresUserRepo):
    u = await users_repo.ensure_user(12345)
    assert u.tg_user_id == 12345
    await users_repo.set_language(12345, "en")
    lang = await users_repo.get_language(12345)
    assert lang == "en"


@pytest.mark.asyncio
async def test_products_crud_and_history(users_repo, products_repo, session):
    user = await users_repo.ensure_user(1001)
    pid = await products_repo.create(
        user_id=user.id,
        url="https://www.ozon.ru/item/42",
        title="Widget",
        target_price=99.99,
        current_price=149.99,
    )
    assert pid > 0

    pid2 = await products_repo.create(
        user_id=user.id,
        url="https://www.ozon.ru/item/42",
        title="Widget",
        target_price=199.99,
        current_price=None,
    )
    assert pid2 == pid

    total = await products_repo.count_by_user(user.id)
    assert total == 1
    items, pages = await products_repo.list_page(user.id, page=1, page_size=PAGE_SIZE)
    assert len(items) == 1 and pages == 1

    await products_repo.add_price_history(pid, 149.99, source="add")
    latest = await products_repo.get_latest_price(pid)
    assert latest is not None
    price, when = latest
    assert price == 149.99 and isinstance(when, str)

    await products_repo.update_target_price(pid, 79.99)
    prod = await products_repo.get_by_id(pid)
    assert prod and prod.target_price == 79.99

    await products_repo.update_current_and_history(pid, 120.50, source="scheduler")
    latest2 = await products_repo.get_latest_price(pid)
    assert latest2 and latest2[0] == 120.50

    await products_repo.delete(pid)
    assert await products_repo.get_by_id(pid) is None


@pytest.mark.asyncio
async def test_pagination_many_items(users_repo, products_repo):
    u = await users_repo.ensure_user(2001)
    n = PAGE_SIZE * 2 + 1
    for i in range(n):
        await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/{i}",
            title=f"Item {i}",
            target_price=10.0 + i,
            current_price=None,
        )
    items1, pages = await products_repo.list_page(u.id, page=1, page_size=PAGE_SIZE)
    items2, _ = await products_repo.list_page(u.id, page=2, page_size=PAGE_SIZE)
    items3, _ = await products_repo.list_page(u.id, page=3, page_size=PAGE_SIZE)
    assert pages == 3
    assert len(items1) == PAGE_SIZE
    assert len(items2) == PAGE_SIZE
    assert len(items3) == 1
