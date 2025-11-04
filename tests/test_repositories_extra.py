import pytest


@pytest.mark.asyncio
async def test_list_all_active_and_state(users_repo, products_repo):
    u = await users_repo.ensure_user(4242)
    ids = []
    for i in range(3):
        pid = await products_repo.create(
            user_id=u.id,
            url=f"https://www.ozon.ru/item/active{i}",
            title=f"A{i}",
            target_price=10 + i,
            current_price=None,
        )
        ids.append(pid)

    seen = []
    async for p in products_repo.list_all_active():
        if p.user_id == u.id:
            seen.append(p.id)
    assert set(ids).issubset(set(seen))

    await products_repo.set_last_state(ids[0], "below", last_notified_price=9.99)
    p = await products_repo.get_by_id(ids[0])
    assert p.last_state == "below" and p.last_notified_price == 9.99
