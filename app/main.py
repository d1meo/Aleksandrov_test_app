"""
Точка входа — тут всё стартует и всё умирает.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.database import close_pool, create_pool
from app.routers import students, upload


# ---------------------------------------------------------------------------
# Жизненный цикл приложения
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Поднимаем пул коннектов при старте, гасим при завершении."""
    await create_pool()
    yield
    await close_pool()


# ---------------------------------------------------------------------------
# Само приложение
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Хелсчек — чтобы деплой не гадал, живы ли мы
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"], summary="Проверка работоспособности сервиса")
async def health() -> dict[str, str]:
    return {"status": "ok"}
