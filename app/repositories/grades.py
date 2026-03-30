"""
Слой доступа к данным — весь SQL сосредоточен здесь.

Роутеры и сервисы не знают про asyncpg и SQL-запросы.
"""

from asyncpg import Connection

from app.validators import GradeRecord


async def upsert_student(conn: Connection, full_name: str, group_number: str) -> int:
    """Вставляем студента или получаем его id если уже существует."""
    return await conn.fetchval(
        """
        INSERT INTO students (full_name, group_number)
        VALUES ($1, $2)
        ON CONFLICT ON CONSTRAINT uq_students_name_group
            DO UPDATE SET full_name = EXCLUDED.full_name
        RETURNING id
        """,
        full_name,
        group_number,
    )


async def insert_grade(conn: Connection, student_id: int, grade: int, date) -> bool:
    """Вставляем оценку. Возвращает True если строка реально вставлена."""
    result = await conn.execute(
        """
        INSERT INTO grades (student_id, grade, date)
        VALUES ($1, $2, $3)
        ON CONFLICT ON CONSTRAINT uq_grades_student_date
            DO NOTHING
        """,
        student_id,
        grade,
        date,
    )
    try:
        return int(str(result).split()[-1]) > 0
    except (ValueError, IndexError):
        return False


async def get_students_with_twos_more_than(conn: Connection, threshold: int) -> list[dict]:
    """Студенты с количеством двоек строго больше threshold."""
    rows = await conn.fetch(
        """
        SELECT
            s.full_name,
            COUNT(g.id) AS count_twos
        FROM grades g
        JOIN students s ON s.id = g.student_id
        WHERE g.grade = 2
        GROUP BY s.id, s.full_name
        HAVING COUNT(g.id) > $1
        ORDER BY count_twos DESC, s.full_name
        """,
        threshold,
    )
    return [dict(r) for r in rows]


async def get_students_with_twos_less_than(conn: Connection, threshold: int) -> list[dict]:
    """Студенты с количеством двоек строго меньше threshold (но хотя бы одна)."""
    rows = await conn.fetch(
        """
        SELECT
            s.full_name,
            COUNT(g.id) AS count_twos
        FROM grades g
        JOIN students s ON s.id = g.student_id
        WHERE g.grade = 2
        GROUP BY s.id, s.full_name
        HAVING COUNT(g.id) < $1
        ORDER BY count_twos DESC, s.full_name
        """,
        threshold,
    )
    return [dict(r) for r in rows]
