"""
Конфиг pytest и шаред-фикстуры.

Архитектурный выбор: тесты гоняются без реального PostgreSQL.
Оба роутера делают `from app.database import get_connection` — прямой биндинг имени.
Это значит патчить `app.database.get_connection` бесполезно — имя уже связано.
Патчим в неймспейсе каждого роутера напрямую.
"""

import os
from pathlib import Path
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Пути к фикстурам
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def csv_bytes(content: str) -> bytes:
    """Кодируем строку в UTF-8 с BOM — как и настоящие CSV-файлы."""
    return ("\ufeff" + content).encode("utf-8")


def load_fixture(name: str) -> bytes:
    """Читаем фикстурный CSV-файл как байты."""
    return (FIXTURES_DIR / name).read_bytes()


# ---------------------------------------------------------------------------
# Патчим настройки до первого импорта приложения
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _patch_settings():
    """Подсовываем фейковый DATABASE_URL — pydantic-settings не ломается без .env."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        yield


# ---------------------------------------------------------------------------
# Мок asyncpg-коннекта
# ---------------------------------------------------------------------------

def make_mock_connection():
    """Собираем фейковый asyncpg Connection.

    Важные нюансы:
    - conn.transaction() должен возвращать async-контекстный менеджер, а не корутину.
      У asyncpg это обычный метод, возвращающий объект с __aenter__/__aexit__.
      Поэтому используем MagicMock(return_value=_FakeTx()), а не AsyncMock.
    - conn.execute() — async-метод, возвращает строку типа "INSERT 0 1".
    - conn.fetch() — async-метод, возвращает список записей.
    - conn.fetchval() — async-метод, возвращает скаляр.
    """
    conn = MagicMock()

    class _FakeTx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False

    conn.transaction = MagicMock(return_value=_FakeTx())
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch    = AsyncMock(return_value=[])
    conn.execute  = AsyncMock(return_value="INSERT 0 1")

    return conn


@pytest.fixture()
def mock_conn():
    """Свежий мок-коннект на каждый тест."""
    return make_mock_connection()


# ---------------------------------------------------------------------------
# Патчим get_connection в обоих роутерах
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_db(mock_conn):
    """Подменяем get_connection прямо в неймспейсе каждого роутера.

    Если патчить только app.database, уже импортированные имена не затрагиваются —
    это классическая ловушка при мокировании через from-импорты.
    """

    @asynccontextmanager
    async def _fake_get_connection() -> AsyncGenerator:
        yield mock_conn

    with (
        patch("app.routers.upload.get_connection",  new=_fake_get_connection),
        patch("app.routers.students.get_connection", new=_fake_get_connection),
    ):
        yield mock_conn


# ---------------------------------------------------------------------------
# Async HTTP-клиент для тестов
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(patch_db):
    """AsyncClient поверх FastAPI-приложения. Lifespan скипаем — база замокана."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
