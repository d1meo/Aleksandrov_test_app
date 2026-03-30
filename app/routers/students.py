"""
Аналитические ручки:

  GET /students/more-than-3-twos   — студенты с количеством двоек > 3
  GET /students/less-than-5-twos   — студенты с количеством двоек < 5
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.exceptions import DatabaseError
from app.services import grades as grades_service

router = APIRouter(prefix="/students", tags=["students"])
logger = logging.getLogger(__name__)


class StudentTwosResponse(BaseModel):
    full_name: str
    count_twos: int


@router.get(
    "/more-than-3-twos",
    response_model=list[StudentTwosResponse],
    summary="Студенты с оценкой 2 больше 3 раз",
)
async def students_more_than_3_twos() -> list[StudentTwosResponse]:
    """Возвращает студентов, у которых двойка встречается строго больше 3 раз."""
    try:
        logger.info("Fetching students with more than 3 twos")
        rows = await grades_service.get_students_more_than_3_twos()
        logger.info(f"Found {len(rows)} students with more than 3 twos")
        return [StudentTwosResponse(**row) for row in rows]
    except DatabaseError as exc:
        logger.error(f"Database error fetching students with more than 3 twos: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен. Попробуйте позже."
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error fetching students with more than 3 twos: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера."
        ) from exc


@router.get(
    "/less-than-5-twos",
    response_model=list[StudentTwosResponse],
    summary="Студенты с оценкой 2 меньше 5 раз",
)
async def students_less_than_5_twos() -> list[StudentTwosResponse]:
    """Возвращает студентов, у которых двойка встречается строго меньше 5 раз.

    Студенты без единой двойки в выборку не попадают.
    """
    try:
        logger.info("Fetching students with less than 5 twos")
        rows = await grades_service.get_students_less_than_5_twos()
        logger.info(f"Found {len(rows)} students with less than 5 twos")
        return [StudentTwosResponse(**row) for row in rows]
    except DatabaseError as exc:
        logger.error(f"Database error fetching students with less than 5 twos: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Сервис временно недоступен. Попробуйте позже."
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error fetching students with less than 5 twos: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Внутренняя ошибка сервера."
        ) from exc
