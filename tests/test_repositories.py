from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.products import PAGE_SIZE
from app.repositories.users import PostgresUserRepo
from app.utils.telegram_helpers import TelegramUserData, extract_user_data


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


@pytest.mark.asyncio
async def test_ensure_user_creates_with_telegram_data(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    user = await repo.ensure_user(
        tg_user_id=77777,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_bot=False,
        is_premium=True,
    )

    assert user.tg_user_id == 77777
    assert user.username == "testuser"
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.is_bot is False
    assert user.is_premium is True
    assert user.total_interactions == 1
    assert user.last_active_at is not None
    assert user.notifications_enabled is True


@pytest.mark.asyncio
async def test_ensure_user_updates_existing_user(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    user1 = await repo.ensure_user(
        tg_user_id=88888,
        username="oldusername",
        first_name="Old",
        is_premium=False,
    )
    assert user1.username == "oldusername"
    assert user1.total_interactions == 1
    assert user1.is_premium is False

    user2 = await repo.ensure_user(
        tg_user_id=88888,
        username="newusername",
        first_name="New",
        is_premium=True,
    )

    assert user2.id == user1.id
    assert user2.username == "newusername"
    assert user2.first_name == "New"
    assert user2.is_premium is True
    assert user2.total_interactions == 2
    assert user2.last_active_at != user1.last_active_at


@pytest.mark.asyncio
async def test_ensure_user_backwards_compatible(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    user = await repo.ensure_user(tg_user_id=99999)

    assert user.tg_user_id == 99999
    assert user.username is None
    assert user.first_name is None
    assert user.last_name is None
    assert user.is_bot is False
    assert user.is_premium is False
    assert user.total_interactions == 1


@pytest.mark.asyncio
async def test_set_notifications(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    await repo.ensure_user(tg_user_id=55555)

    await repo.set_notifications(55555, False)
    user = await repo.get_by_tg_id(55555)
    assert user is not None
    assert user.notifications_enabled is False

    await repo.set_notifications(55555, True)
    user = await repo.get_by_tg_id(55555)
    assert user is not None
    assert user.notifications_enabled is True


@pytest.mark.asyncio
async def test_set_timezone(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    await repo.ensure_user(tg_user_id=66666)

    await repo.set_timezone(66666, "Europe/Moscow")
    user = await repo.get_by_tg_id(66666)
    assert user is not None
    assert user.timezone == "Europe/Moscow"


@pytest.mark.asyncio
async def test_update_activity(session: AsyncSession) -> None:
    repo = PostgresUserRepo(session)

    user1 = await repo.ensure_user(tg_user_id=44444)
    initial_interactions = user1.total_interactions
    initial_active = user1.last_active_at

    await repo.update_activity(44444)

    user2 = await repo.get_by_tg_id(44444)
    assert user2 is not None
    assert user2.total_interactions == initial_interactions + 1
    assert user2.last_active_at != initial_active


def test_extract_user_data() -> None:
    tg_user = SimpleNamespace(
        id=12345,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_bot=False,
        is_premium=True,
    )

    data = extract_user_data(tg_user)  # type: ignore

    assert isinstance(data, TelegramUserData)
    assert data.tg_user_id == 12345
    assert data.username == "testuser"
    assert data.first_name == "Test"
    assert data.last_name == "User"
    assert data.is_bot is False
    assert data.is_premium is True


def test_extract_user_data_minimal() -> None:
    tg_user = SimpleNamespace(
        id=99999,
        first_name="Minimal",
        username=None,
        last_name=None,
        is_bot=False,
    )

    data = extract_user_data(tg_user)  # type: ignore

    assert data.tg_user_id == 99999
    assert data.username is None
    assert data.first_name == "Minimal"
    assert data.last_name is None
    assert data.is_bot is False
