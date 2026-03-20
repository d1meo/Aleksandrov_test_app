"""
Пул соединений с PostgreSQL через asyncpg.

Использование:
    from app.database import get_connection

    @router.get("/example")
    async def example():
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT 1")
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Connection, Pool

from app.config import settings

# Пул живёт на уровне модуля — создаётся один раз при старте приложения.
_pool: Pool | None = None


async def create_pool() -> None:
    """Инициализируем пул. Вызывается из lifespan при старте."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )


async def close_pool() -> None:
    """Аккуратно закрываем все коннекты при завершении. Не теряем данные."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Connection, None]:
    """Берём коннект из пула как async-контекстный менеджер.

    Пример::

        async with get_connection() as conn:
            await conn.execute("INSERT INTO ...")
    """
    if _pool is None:
        raise RuntimeError("Пул не инициализирован — сначала вызови create_pool().")
    async with _pool.acquire() as connection:
        yield connection
