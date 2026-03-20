"""
POST /upload-grades — принимаем CSV, валидируем, льём в базу.
"""

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.database import get_connection
from app.validators import CSVValidationError, GradeRecord, parse_and_validate_csv

router = APIRouter(tags=["upload"])


# ---------------------------------------------------------------------------
# Схема ответа
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    status: str
    records_loaded: int
    students: int


# ---------------------------------------------------------------------------
# Эндпоинт
# ---------------------------------------------------------------------------

@router.post(
    "/upload-grades",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Загрузить CSV с успеваемостью студентов",
)
async def upload_grades(file: UploadFile) -> UploadResponse:
    """Загружаем CSV и сохраняем данные в базу.

    - **file**: CSV-файл (разделитель «;», кодировка UTF-8 или UTF-8-BOM).

    Ожидаемые колонки: `Дата`, `Номер группы`, `ФИО`, `Оценка`
    """
    # ---- базовые проверки файла -------------------------------------------
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

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Загруженный файл пустой.",
        )

    # ---- парсим и валидируем CSV ------------------------------------------
    try:
        records: list[GradeRecord] = parse_and_validate_csv(content)
    except CSVValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # ---- пишем в базу ------------------------------------------------------
    _, student_ids = await _upsert_records(records)

    # records_loaded — сколько строк из CSV прошло валидацию и попало в обработку.
    # Именно это число ожидается в ответе по условию задачи.
    return UploadResponse(
        status="ok",
        records_loaded=len(records),
        students=len(student_ids),
    )


# ---------------------------------------------------------------------------
# Работа с базой
# ---------------------------------------------------------------------------

async def _upsert_records(records: list[GradeRecord]) -> tuple[int, set[int]]:
    """Апсёртим записи в одной транзакции.

    Возвращаем (количество_вставленных_строк, множество_id_студентов).
    Повторная загрузка того же файла безопасна — дубли тихо скипаем.
    """
    records_loaded = 0
    student_ids: set[int] = set()

    async with get_connection() as conn:
        async with conn.transaction():
            for rec in records:
                # Апсёртим студента и получаем его id — если уже есть, просто берём существующий.
                student_id: int = await conn.fetchval(
                    """
                    INSERT INTO students (full_name, group_number)
                    VALUES ($1, $2)
                    ON CONFLICT ON CONSTRAINT uq_students_name_group
                        DO UPDATE SET full_name = EXCLUDED.full_name
                    RETURNING id
                    """,
                    rec.full_name,
                    rec.group_number,
                )
                student_ids.add(student_id)

                # Вставляем оценку; если такая уже есть на эту дату — скипаем без ошибки.
                result = await conn.execute(
                    """
                    INSERT INTO grades (student_id, grade, date)
                    VALUES ($1, $2, $3)
                    ON CONFLICT ON CONSTRAINT uq_grades_student_date
                        DO NOTHING
                    """,
                    student_id,
                    rec.grade,
                    rec.date,
                )
                # asyncpg возвращает строку вида "INSERT 0 1" или "INSERT 0 0".
                # Последний токен — количество реально вставленных строк.
                try:
                    inserted = int(str(result).split()[-1])
                except (ValueError, IndexError):
                    inserted = 0
                records_loaded += inserted

    return records_loaded, student_ids
