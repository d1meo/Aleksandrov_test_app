"""
POST /upload-grades — принимаем CSV, передаём в сервисный слой для валидации и обработки.
"""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import settings
from app.exceptions import DatabaseError, ValidationError
from app.services import grades as grades_service

router = APIRouter(tags=["upload"])
logger = logging.getLogger(__name__)


class UploadResponse(BaseModel):
    status: str
    records_loaded: int
    students: int


@router.post(
    "/upload-grades",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Загрузить CSV с успеваемостью студентов",
)
async def upload_grades(file: UploadFile) -> UploadResponse:
    """Загружаем CSV и сохраняем данные в базу.

    - **file**: CSV-файл (разделитель «;», кодировка UTF-8 или UTF-8-BOM).
    - **Ограничения**: Максимальный размер {settings.max_upload_size_mb}MB

    Ожидаемые колонки: `Дата`, `Номер группы`, `ФИО`, `Оценка`
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Имя файла отсутствует.",
        )
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ожидался файл с расширением .csv, получен: '{file.filename}'.",
        )

    # Проверяем размер файла
    MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024
    
    # Читаем файл
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл слишком большой. Максимальный размер: {settings.max_upload_size_mb}MB",
        )
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Загруженный файл пустой.",
        )

    try:
        logger.info(f"Processing upload request for file: {file.filename} ({len(content)} bytes)")
        result = await grades_service.validate_and_upload_csv(content)
        logger.info(f"Upload successful: {result.records_loaded} records, {result.students} students")
        
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except DatabaseError as exc:
        logger.error(f"Database error during upload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис временно недоступен. Попробуйте позже.",
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error during upload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера.",
        ) from exc

    return UploadResponse(
        status="ok",
        records_loaded=result.records_loaded,
        students=result.students,
    )
