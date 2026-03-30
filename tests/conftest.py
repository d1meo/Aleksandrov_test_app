"""
Конфиг pytest и общие фикстуры.

Тесты гоняются без реального PostgreSQL.
Роутеры вызывают сервисы, сервисы вызывают get_connection из app.database.
Патчим get_connection в неймспейсе сервисного модуля напрямую — это
единственный надёжный способ при from-импортах.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def csv_bytes(content: str) -> bytes:
    """Кодируем строку в UTF-8 с BOM — как и настоящие CSV-файлы."""
    return ("\ufeff" + content).encode("utf-8")


def load_fixture(name: str) -> bytes:
    """Читаем фикстурный CSV-файл как байты."""
    return (FIXTURES_DIR / name).read_bytes()


@pytest.fixture(scope="session", autouse=True)
def _patch_settings():
    """Подсовываем фейковый DATABASE_URL — pydantic-settings не ломается без .env."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
        yield


def make_mock_connection():
    """Собираем фейковый asyncpg Connection.

    conn.transaction() возвращает sync-объект с __aenter__/__aexit__,
    а не корутину — именно так работает asyncpg.
    """
    conn = MagicMock()

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    conn.transaction = MagicMock(return_value=_FakeTx())
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    return conn


@pytest.fixture()
def mock_conn():
    """Свежий мок-коннект на каждый тест."""
    return make_mock_connection()


@pytest.fixture()
def patch_db(mock_conn):
    """Подменяем get_connection в сервисном слое.

    Сервисы используют from app.database import get_connection — патчим
    именно в их неймспейсе, иначе мок не сработает.
    """

    @asynccontextmanager
    async def _fake_get_connection() -> AsyncGenerator:
        yield mock_conn

    with (
        patch("app.services.grades.get_connection", new=_fake_get_connection),
    ):
        yield mock_conn


@pytest_asyncio.fixture()
async def client(patch_db):
    """AsyncClient поверх FastAPI-приложения. Lifespan пропускаем — база замокана."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
