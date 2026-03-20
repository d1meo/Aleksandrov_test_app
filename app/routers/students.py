"""
Аналитические ручки — смотрим кто конкретно не вывозит учёбу.

  GET /students/more-than-3-twos   — двоечники хардкорные (двоек > 3)
  GET /students/less-than-5-twos   — двоечники лайтовые (двоек < 5, но хотя бы одна)
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.database import get_connection

router = APIRouter(prefix="/students", tags=["students"])


# ---------------------------------------------------------------------------
# Схема ответа
# ---------------------------------------------------------------------------

class StudentTwosResponse(BaseModel):
    full_name: str
    count_twos: int


# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.get(
    "/more-than-3-twos",
    response_model=list[StudentTwosResponse],
    summary="Студенты с оценкой 2 больше 3 раз",
)
async def students_more_than_3_twos() -> list[StudentTwosResponse]:
    """Возвращаем тех, у кого двойка встречается строго больше 3 раз."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.full_name,
                COUNT(g.id) AS count_twos
            FROM grades  g
            JOIN students s ON s.id = g.student_id
            WHERE g.grade = 2
            GROUP BY s.id, s.full_name
            HAVING COUNT(g.id) > 3
            ORDER BY count_twos DESC, s.full_name
            """
        )
    return [StudentTwosResponse(full_name=r["full_name"], count_twos=r["count_twos"]) for r in rows]


@router.get(
    "/less-than-5-twos",
    response_model=list[StudentTwosResponse],
    summary="Студенты с оценкой 2 меньше 5 раз",
)
async def students_less_than_5_twos() -> list[StudentTwosResponse]:
    """Возвращаем тех, у кого двойка встречается строго меньше 5 раз.
    Студенты без единой двойки в выборку не попадают — они тут ни при чём.
    """
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.full_name,
                COUNT(g.id) AS count_twos
            FROM grades  g
            JOIN students s ON s.id = g.student_id
            WHERE g.grade = 2
            GROUP BY s.id, s.full_name
            HAVING COUNT(g.id) < 5
            ORDER BY count_twos DESC, s.full_name
            """
        )
    return [StudentTwosResponse(full_name=r["full_name"], count_twos=r["count_twos"]) for r in rows]
