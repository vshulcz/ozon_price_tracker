from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.repositories.products import ProductsRepo
from app.repositories.users import PostgresUserRepo


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.sqlite3"
    return path


@pytest.fixture(scope="session")
async def engine(tmp_db_path):
    url = f"sqlite+aiosqlite:///{tmp_db_path}"
    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def session_maker(engine):
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(session_maker):
    async with session_maker() as s:
        yield s


@pytest.fixture
def users_repo(session):
    return PostgresUserRepo(session)


@pytest.fixture
def products_repo(session):
    return ProductsRepo(session)


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, reply_markup=None, disable_web_page_preview=False):
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "disable_web_page_preview": disable_web_page_preview,
            }
        )


@pytest.fixture
def fake_bot():
    return FakeBot()


class DummyMessage:
    _id_counter = 0

    def __init__(self, user_id=1000, chat_id=1):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        DummyMessage._id_counter += 1
        self.message_id = DummyMessage._id_counter

        self.text: str | None = None
        self.answers = []
        self.edits = []
        self.children = []

    async def answer(self, text, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})
        child = DummyMessage(user_id=self.from_user.id, chat_id=self.chat.id)
        self.children.append(child)
        return child

    async def edit_text(self, text, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})


class DummyCallbackQuery:
    def __init__(self, message: DummyMessage | None = None, user_id=1000):
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message or DummyMessage(user_id=user_id)
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})


class FakeFSMContext:
    def __init__(self):
        self._state = None
        self._data = {}

    @staticmethod
    def _state_name(s):
        return getattr(s, "state", s)

    async def set_state(self, s):
        self._state = self._state_name(s)

    async def get_state(self):
        return self._state

    async def clear(self):
        self._state = None
        self._data = {}

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def get_data(self):
        return dict(self._data)


@pytest.fixture
def dummy_message():
    return DummyMessage()


@pytest.fixture
def dummy_cb(dummy_message):
    return DummyCallbackQuery(message=dummy_message)


@pytest.fixture
def fsm():
    return FakeFSMContext()
