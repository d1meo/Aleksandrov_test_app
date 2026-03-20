"""
Валидация CSV с оценками студентов.

Ожидаемый формат (разделитель — точка с запятой, кодировка UTF-8 / UTF-8-BOM):
    Дата;Номер группы;ФИО;Оценка
    11.03.2025;101Б;Курочкин Антон Владимирович;4
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = {"Дата", "Номер группы", "ФИО", "Оценка"}
CSV_DELIMITER = ";"
DATE_FORMAT = "%d.%m.%Y"
VALID_GRADES = frozenset(range(1, 6))  # допустимые оценки: 1..5


# ---------------------------------------------------------------------------
# Модель данных
# ---------------------------------------------------------------------------

@dataclass(slots=True, frozen=True)
class GradeRecord:
    """Одна провалидированная строка из CSV."""

    full_name: str
    group_number: str
    grade: int
    date: date


# ---------------------------------------------------------------------------
# Исключение
# ---------------------------------------------------------------------------

class CSVValidationError(ValueError):
    """Бросается когда файл или строка в нём не прошли валидацию."""


# ---------------------------------------------------------------------------
# Публичный интерфейс
# ---------------------------------------------------------------------------

def parse_and_validate_csv(content: bytes) -> list[GradeRecord]:
    """Парсим и валидируем сырые байты загруженного CSV.

    При структурных проблемах кидаем исключение сразу.
    Ошибки по отдельным строкам собираем все разом и отдаём одним сообщением —
    чтобы пользователь не фиксил файл итерационно по одной строке.
    """
    # Декодируем — BOM в начале файла тихо срезаем, он нам не нужен.
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVValidationError(f"Не удалось декодировать файл как UTF-8: {exc}") from exc

    if not text.strip():
        raise CSVValidationError("Файл пустой.")

    reader = csv.DictReader(io.StringIO(text), delimiter=CSV_DELIMITER)

    # ---- проверяем заголовок -----------------------------------------------
    if reader.fieldnames is None:
        raise CSVValidationError("Не удалось прочитать заголовок CSV.")

    # На всякий случай срезаем пробелы с названий колонок.
    actual_columns = {col.strip() for col in reader.fieldnames}
    missing = REQUIRED_COLUMNS - actual_columns
    if missing:
        raise CSVValidationError(
            f"Отсутствуют обязательные колонки: {', '.join(sorted(missing))}. "
            f"Ожидались: {', '.join(sorted(REQUIRED_COLUMNS))}."
        )

    # ---- валидируем строки -------------------------------------------------
    records: list[GradeRecord] = []
    row_errors: list[str] = []

    for line_no, row in enumerate(reader, start=2):  # start=2 — первая строка это хедер
        errors = _validate_row(row, line_no)
        if errors:
            row_errors.extend(errors)
            continue

        records.append(
            GradeRecord(
                full_name=row["ФИО"].strip(),
                group_number=row["Номер группы"].strip(),
                grade=int(row["Оценка"].strip()),
                date=datetime.strptime(row["Дата"].strip(), DATE_FORMAT).date(),
            )
        )

    if row_errors:
        # Показываем максимум 20 ошибок — иначе ответ превратится в простыню.
        sample = row_errors[:20]
        suffix = f" (показаны первые 20 из {len(row_errors)})" if len(row_errors) > 20 else ""
        raise CSVValidationError("Ошибки валидации строк:\n" + "\n".join(sample) + suffix)

    if not records:
        raise CSVValidationError("CSV не содержит ни одной валидной строки с данными.")

    return records


# ---------------------------------------------------------------------------
# Внутренние хелперы
# ---------------------------------------------------------------------------

def _validate_row(row: dict[str, str | None], line_no: int) -> list[str]:
    """Возвращаем список ошибок для строки. Пустой список — строка ок."""
    errors: list[str] = []

    # --- ФИО ----------------------------------------------------------------
    full_name = (row.get("ФИО") or "").strip()
    if not full_name:
        errors.append(f"Строка {line_no}: ФИО не может быть пустым.")

    # --- Номер группы -------------------------------------------------------
    group_number = (row.get("Номер группы") or "").strip()
    if not group_number:
        errors.append(f"Строка {line_no}: Номер группы не может быть пустым.")

    # --- Оценка -------------------------------------------------------------
    raw_grade = (row.get("Оценка") or "").strip()
    if not raw_grade:
        errors.append(f"Строка {line_no}: Оценка не может быть пустой.")
    else:
        try:
            grade_int = int(raw_grade)
        except ValueError:
            errors.append(
                f"Строка {line_no}: Оценка '{raw_grade}' не является целым числом."
            )
        else:
            if grade_int not in VALID_GRADES:
                errors.append(
                    f"Строка {line_no}: Оценка {grade_int} вне допустимого диапазона (1–5)."
                )

    # --- Дата ---------------------------------------------------------------
    raw_date = (row.get("Дата") or "").strip()
    if not raw_date:
        errors.append(f"Строка {line_no}: Дата не может быть пустой.")
    else:
        try:
            datetime.strptime(raw_date, DATE_FORMAT)
        except ValueError:
            errors.append(
                f"Строка {line_no}: Дата '{raw_date}' не соответствует формату ДД.ММ.ГГГГ."
            )

    return errors
