"""
Юнит-тесты для app.validators — чистый Python, без БД и HTTP.

Проверяем логику парсинга и валидации CSV в изоляции.
"""

import pytest
from app.validators import CSVValidationError, GradeRecord, parse_and_validate_csv


# ---------------------------------------------------------------------------
# Хелпер
# ---------------------------------------------------------------------------

def make_csv(*rows: str, header: str = "Дата;Номер группы;ФИО;Оценка") -> bytes:
    """Собираем минимальный UTF-8-BOM CSV из переданных строк."""
    lines = [header] + list(rows)
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


VALID_ROW = "01.01.2025;101Б;Иванов Иван Иванович;4"


# ---------------------------------------------------------------------------
# Хэппи-пас
# ---------------------------------------------------------------------------

class TestParseValid:

    def test_single_valid_row(self):
        result = parse_and_validate_csv(make_csv(VALID_ROW))
        assert len(result) == 1
        rec = result[0]
        assert isinstance(rec, GradeRecord)
        assert rec.full_name == "Иванов Иван Иванович"
        assert rec.group_number == "101Б"
        assert rec.grade == 4
        assert rec.date.year == 2025
        assert rec.date.month == 1
        assert rec.date.day == 1

    def test_all_valid_grades(self):
        rows = [f"0{i}.01.2025;101Б;Студент{i};{i}" for i in range(1, 6)]
        result = parse_and_validate_csv(make_csv(*rows))
        grades = [r.grade for r in result]
        assert grades == [1, 2, 3, 4, 5]

    def test_utf8_without_bom(self):
        content = "Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;3\n".encode("utf-8")
        result = parse_and_validate_csv(content)
        assert len(result) == 1

    def test_strips_whitespace_around_values(self):
        # Пробелы вокруг значений — срезаем, не падаем.
        content = make_csv(" 01.01.2025 ; 101Б ; Иванов Иван ; 4 ")
        result = parse_and_validate_csv(content)
        assert result[0].full_name == "Иванов Иван"
        assert result[0].grade == 4

    def test_two_name_parts_accepted(self):
        """ФИО из двух слов (без отчества) тоже валидно."""
        result = parse_and_validate_csv(make_csv("01.01.2025;101Б;Иванов Иван;5"))
        assert result[0].full_name == "Иванов Иван"


# ---------------------------------------------------------------------------
# Ошибки на уровне файла
# ---------------------------------------------------------------------------

class TestFileErrors:

    def test_empty_bytes(self):
        with pytest.raises(CSVValidationError, match="пуст"):
            parse_and_validate_csv(b"")

    def test_only_whitespace(self):
        with pytest.raises(CSVValidationError, match="пуст"):
            parse_and_validate_csv(b"   \n  ")

    def test_header_only_no_rows(self):
        with pytest.raises(CSVValidationError):
            parse_and_validate_csv(make_csv())  # только хедер, данных нет

    def test_non_utf8_bytes(self):
        # Windows-1251 — не UTF-8, падаем с понятным сообщением.
        garbage = b"\xcf\xf0\xe8\xec\xe5\xf0"
        with pytest.raises(CSVValidationError, match="UTF-8"):
            parse_and_validate_csv(garbage)


# ---------------------------------------------------------------------------
# Ошибки заголовка / колонок
# ---------------------------------------------------------------------------

class TestHeaderErrors:

    def test_missing_grade_column(self):
        content = make_csv(VALID_ROW, header="Дата;Номер группы;ФИО")
        with pytest.raises(CSVValidationError, match="Оценка"):
            parse_and_validate_csv(content)

    def test_missing_date_column(self):
        content = make_csv(VALID_ROW, header="Номер группы;ФИО;Оценка")
        with pytest.raises(CSVValidationError, match="Дата"):
            parse_and_validate_csv(content)

    def test_missing_fio_column(self):
        content = make_csv(VALID_ROW, header="Дата;Номер группы;Оценка")
        with pytest.raises(CSVValidationError, match="ФИО"):
            parse_and_validate_csv(content)

    def test_wrong_delimiter_comma(self):
        # Запятая вместо точки с запятой — колонки не распознаются.
        content = "Дата,Номер группы,ФИО,Оценка\n01.01.2025,101Б,Тест,4\n".encode("utf-8")
        with pytest.raises(CSVValidationError):
            parse_and_validate_csv(content)

    def test_extra_columns_are_ignored(self):
        """Лишние колонки не ломают парсинг — просто игнорируем."""
        content = make_csv(
            "01.01.2025;101Б;Иванов Иван;4;extra_column",
            header="Дата;Номер группы;ФИО;Оценка;Лишнее"
        )
        result = parse_and_validate_csv(content)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Ошибки строк — оценка
# ---------------------------------------------------------------------------

class TestGradeValidation:

    @pytest.mark.parametrize("bad_grade", ["0", "6", "99", "-1"])
    def test_grade_out_of_range(self, bad_grade):
        content = make_csv(f"01.01.2025;101Б;Тест;{bad_grade}")
        with pytest.raises(CSVValidationError, match="диапазон|1–5|range"):
            parse_and_validate_csv(content)

    @pytest.mark.parametrize("bad_grade", ["отлично", "хорошо", "abc", "4.5", ""])
    def test_grade_not_a_valid_int(self, bad_grade):
        content = make_csv(f"01.01.2025;101Б;Тест;{bad_grade}")
        with pytest.raises(CSVValidationError):
            parse_and_validate_csv(content)


# ---------------------------------------------------------------------------
# Ошибки строк — дата
# ---------------------------------------------------------------------------

class TestDateValidation:

    @pytest.mark.parametrize("bad_date", [
        "2025-01-01",  # ISO — не наш формат
        "01/01/2025",  # американский слэш — тоже мимо
        "вчера",       # просто мусор
        "32.01.2025",  # несуществующий день
        "",            # пусто
    ])
    def test_invalid_date(self, bad_date):
        content = make_csv(f"{bad_date};101Б;Тест;4")
        with pytest.raises(CSVValidationError):
            parse_and_validate_csv(content)

    def test_valid_date_boundary(self):
        """31-е число месяца, в котором 31 день — принимаем."""
        result = parse_and_validate_csv(make_csv("31.01.2025;101Б;Тест;4"))
        assert result[0].date.day == 31


# ---------------------------------------------------------------------------
# Ошибки строк — пустые поля
# ---------------------------------------------------------------------------

class TestEmptyFieldValidation:

    def test_empty_fio(self):
        content = make_csv("01.01.2025;101Б;;4")
        with pytest.raises(CSVValidationError, match="ФИО"):
            parse_and_validate_csv(content)

    def test_empty_group(self):
        content = make_csv("01.01.2025;;Тест Тест;4")
        with pytest.raises(CSVValidationError, match="группы|группа"):
            parse_and_validate_csv(content)

    def test_multiple_bad_rows_collected(self):
        """Все ошибки собираются разом — не стопаемся на первой кривой строке."""
        content = make_csv(
            "вчера;101Б;Тест1;9",        # плохая дата + оценка за пределами
            "01.01.2025;102Б;Тест2;abc",  # оценка не число
            "01.02.2025;103Б;;5",          # пустое ФИО
        )
        with pytest.raises(CSVValidationError) as exc_info:
            parse_and_validate_csv(content)
        msg = str(exc_info.value)
        # Номера строк должны быть в сообщении об ошибке
        assert "2" in msg or "3" in msg or "4" in msg
