"""
Точка входа FastAPI-приложения.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException

from app.database import close_pool, create_pool, get_connection
from app.routers import students, upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Поднимаем пул соединений при старте, закрываем при завершении."""
    await create_pool()
    yield
    await close_pool()


app = FastAPI(
    title="Student Grades Service",
    description=(
        "REST API для загрузки CSV-файлов с успеваемостью студентов "
        "и последующего анализа данных."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(upload.router)
app.include_router(students.router)


@app.get("/health", tags=["system"], summary="Проверка работоспособности сервиса")
async def health() -> dict[str, str]:
    """Проверяет доступность сервиса и подключение к БД."""
    try:
        async with get_connection() as conn:
            await conn.fetch("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable. Database connection failed: {str(e)}"
        )
