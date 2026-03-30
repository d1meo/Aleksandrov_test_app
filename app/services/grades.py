"""
Сервисный слой — бизнес-логика приложения.

Сервисы оркестрируют репозитории и не зависят от HTTP-слоя.
"""

import logging
from dataclasses import dataclass

import asyncpg

from app.database import get_connection
from app.exceptions import DatabaseError, ValidationError
from app.repositories import grades as grades_repo
from app.validators import CSVValidationError, GradeRecord, parse_and_validate_csv

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    records_loaded: int
    students: int


async def validate_and_upload_csv(content: bytes) -> UploadResult:
    """Валидирует CSV и сохраняет записи в базу.

    Args:
        content: Содержимое CSV файла в байтах

    Returns:
        UploadResult с количеством загруженных записей и студентов

    Raises:
        ValidationError: Ошибка валидации CSV
        DatabaseError: Ошибка базы данных
    """
    try:
        records = parse_and_validate_csv(content)
        logger.info(f"CSV validation successful, {len(records)} records validated")
    except CSVValidationError as e:
        logger.warning(f"CSV validation failed: {e}")
        raise ValidationError(f"Invalid CSV: {str(e)}") from e
    
    return await upload_grades(records)


async def upload_grades(records: list[GradeRecord]) -> UploadResult:
    """Сохраняем провалидированные записи в базу в одной транзакции.

    Повторная загрузка того же файла безопасна — дубли тихо пропускаются.
    """
    inserted_count = 0
    student_ids: set[int] = set()

    try:
        async with get_connection() as conn:
            async with conn.transaction():
                for rec in records:
                    student_id = await grades_repo.upsert_student(
                        conn, rec.full_name, rec.group_number
                    )
                    student_ids.add(student_id)

                    was_inserted = await grades_repo.insert_grade(
                        conn, student_id, rec.grade, rec.date
                    )
                    if was_inserted:
                        inserted_count += 1
        
        logger.info(f"Successfully uploaded {len(records)} records for {len(student_ids)} students")
        
    except asyncpg.PostgresError as e:
        logger.error(f"Database error during upload: {e}")
        raise DatabaseError(f"Failed to upload grades: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        raise DatabaseError(f"Failed to upload grades: {str(e)}") from e

    return UploadResult(
        records_loaded=len(records),
        students=len(student_ids),
    )


async def get_students_more_than_3_twos() -> list[dict]:
    """Студенты с количеством двоек строго больше 3."""
    try:
        async with get_connection() as conn:
            result = await grades_repo.get_students_with_twos_more_than(conn, threshold=3)
        logger.info(f"Found {len(result)} students with more than 3 twos")
        return result
    except asyncpg.PostgresError as e:
        logger.error(f"Database error fetching students with more than 3 twos: {e}")
        raise DatabaseError(f"Failed to fetch students: {str(e)}") from e


async def get_students_less_than_5_twos() -> list[dict]:
    """Студенты с количеством двоек строго меньше 5 (но хотя бы одна)."""
    try:
        async with get_connection() as conn:
            result = await grades_repo.get_students_with_twos_less_than(conn, threshold=5)
        logger.info(f"Found {len(result)} students with less than 5 twos")
        return result
    except asyncpg.PostgresError as e:
        logger.error(f"Database error fetching students with less than 5 twos: {e}")
        raise DatabaseError(f"Failed to fetch students: {str(e)}") from e
