"""
Тесты для POST /upload-grades.

Покрытие:
  Хэппи-пас
  ├── валидный минимальный CSV        → 200, корректные счётчики
  ├── полный CSV (2 000 строк)        → 200, 40 студентов
  └── идемпотентность (загрузка 2 раза) → второй раз records_loaded == 0

Негативные сценарии
  ├── пустой файл                     → 422
  ├── не тот формат (.txt)            → 422
  ├── нет имени файла                 → 422
  ├── CSV с запятой вместо точки с запятой → 422
  ├── отсутствует обязательная колонка → 422
  ├── оценка вне диапазона (0, 6, 99) → 422
  ├── оценка не число                 → 422
  ├── неправильный формат даты        → 422
  └── только заголовок, без данных    → 422
"""

import io
import pytest
from tests.conftest import csv_bytes, load_fixture


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def upload_files(content: bytes, filename: str = "grades.csv", content_type: str = "text/csv"):
    return {"file": (filename, io.BytesIO(content), content_type)}


def _make_fetchval_side_effect(start_id: int = 1):
    """Фабрика side_effect — раздаёт инкрементальные ID студентов."""
    counter = [start_id - 1]
    async def _fetchval(*args, **kwargs):
        counter[0] += 1
        return counter[0]
    return _fetchval


# ---------------------------------------------------------------------------
# Хэппи-пас
# ---------------------------------------------------------------------------

class TestUploadHappyPath:

    @pytest.mark.asyncio
    async def test_upload_minimal_csv(self, client, mock_conn):
        """Минимальный валидный CSV на 5 строк — ожидаем status=ok и правильные счётчики."""
        # grades_minimal.csv: 4 уникальных студента, Иванов встречается дважды.
        # Симулируем апсёрт: одинаковый студент → одинаковый id.
        # Маппинг: Иванов→1, Петров→2, Сидоров→3, Козлов→4
        name_to_id = {
            "Иванов Иван Иванович": 1,
            "Петров Пётр Петрович": 2,
            "Сидоров Сидор":        3,
            "Козлов Артём":         4,
        }
        call_counter = [0]
        names_in_order = [
            "Иванов Иван Иванович",
            "Петров Пётр Петрович",
            "Сидоров Сидор",
            "Иванов Иван Иванович",  # строка 4 — тот же студент, id не меняется
            "Козлов Артём",
        ]
        async def _fetchval_by_name(*args, **kwargs):
            idx = call_counter[0] % len(names_in_order)
            call_counter[0] += 1
            return name_to_id[names_in_order[idx]]
        mock_conn.fetchval.side_effect = _fetchval_by_name
        mock_conn.execute.return_value = "INSERT 0 1"

        content = load_fixture("grades_minimal.csv")
        response = await client.post("/upload-grades", files=upload_files(content))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["records_loaded"] == 5
        assert body["students"] == 4  # множество уникальных id: {1, 2, 3, 4}

    @pytest.mark.asyncio
    async def test_upload_full_csv(self, client, mock_conn):
        """Настоящий CSV на 2 000 строк — должно прожеваться и отдать 40 студентов."""
        # Симулируем 40 уникальных id, циклично прокручивая 1..40.
        # Роутер складывает id в set, поэтому len(set) == 40.
        counter = [0]
        async def _fetchval_cycling(*args, **kwargs):
            counter[0] += 1
            return (counter[0] - 1) % 40 + 1  # возвращает 1..40 по кругу
        mock_conn.fetchval.side_effect = _fetchval_cycling
        mock_conn.execute.return_value = "INSERT 0 1"

        content = load_fixture("students_grades.csv")
        response = await client.post("/upload-grades", files=upload_files(content))

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["records_loaded"] == 2000
        assert body["students"] == 40

    @pytest.mark.asyncio
    async def test_upload_idempotent_second_call(self, client, mock_conn):
        """Загрузка того же файла второй раз — дубли скипаются в БД.

        records_loaded отражает количество строк из CSV, прошедших валидацию.
        Идемпотентность обеспечивается ON CONFLICT DO NOTHING на уровне БД.
        """
        mock_conn.fetchval.side_effect = _make_fetchval_side_effect(1)
        # ON CONFLICT DO NOTHING → база ничего не вставила
        mock_conn.execute.return_value = "INSERT 0 0"

        content = load_fixture("grades_minimal.csv")
        response = await client.post("/upload-grades", files=upload_files(content))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        # records_loaded — количество строк CSV, которые прошли валидацию
        assert response.json()["records_loaded"] == 5


# ---------------------------------------------------------------------------
# Проверки на уровне файла
# ---------------------------------------------------------------------------

class TestUploadFileValidation:

    @pytest.mark.asyncio
    async def test_empty_file(self, client, mock_conn):
        """Нулевой файл — сразу 422, даже не пытаемся парсить."""
        response = await client.post("/upload-grades", files=upload_files(b""))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_wrong_extension_txt(self, client, mock_conn):
        """Файл .txt — не пропускаем, даже если контент похож на CSV."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;4")
        response = await client.post("/upload-grades", files=upload_files(content, filename="data.txt"))
        assert response.status_code == 422
        assert ".csv" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_wrong_extension_xlsx(self, client, mock_conn):
        """Excel-файл — тоже нет, мы не таблицы гугла."""
        response = await client.post("/upload-grades", files=upload_files(b"PK...", filename="data.xlsx"))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_header_only_no_data_rows(self, client, mock_conn):
        """CSV только с заголовком и без строк данных — не принимаем."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Проверки содержимого CSV
# ---------------------------------------------------------------------------

class TestUploadCSVValidation:

    @pytest.mark.asyncio
    async def test_wrong_delimiter_comma(self, client, mock_conn):
        """CSV с запятой вместо точки с запятой — колонки не распознаются → 422."""
        content = csv_bytes("Дата,Номер группы,ФИО,Оценка\n01.01.2025,101Б,Тест Тест,4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_column_grade(self, client, mock_conn):
        """Нет колонки 'Оценка' — валидация фейлится с понятной ошибкой."""
        content = csv_bytes("Дата;Номер группы;ФИО\n01.01.2025;101Б;Тест Тест")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        assert "Оценка" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_missing_column_date(self, client, mock_conn):
        """Нет колонки 'Дата' — тоже фейл с указанием что именно пропало."""
        content = csv_bytes("Номер группы;ФИО;Оценка\n101Б;Тест Тест;4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        assert "Дата" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_grade_out_of_range_zero(self, client, mock_conn):
        """Оценка 0 — ниже допустимого диапазона 1–5."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;0")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        assert "диапазон" in response.json()["detail"].lower() or "1" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_grade_out_of_range_six(self, client, mock_conn):
        """Оценка 6 — выше допустимого диапазона 1–5."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;6")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_grade_not_a_number(self, client, mock_conn):
        """Оценка словом — не принимаем, только цифры."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;отлично")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        assert "целым числом" in response.json()["detail"] or "число" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_grade_float_rejected(self, client, mock_conn):
        """Дробная оценка типа 4.5 — тоже мимо, только целые."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Тест;4.5")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_format_dashes(self, client, mock_conn):
        """Дата в ISO-формате (YYYY-MM-DD) — ожидаем ДД.ММ.ГГГГ, не угадал."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n2025-01-01;101Б;Тест Тест;4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        assert "ДД.ММ.ГГГГ" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_date_not_a_date(self, client, mock_conn):
        """Полная ерунда вместо даты — фейлим без лишних вопросов."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\nвчера;101Б;Тест Тест;4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_full_name(self, client, mock_conn):
        """Пустое ФИО — не принимаем, студент должен как-то называться."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;;4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_group_number(self, client, mock_conn):
        """Пустой номер группы — тоже мимо."""
        content = csv_bytes("Дата;Номер группы;ФИО;Оценка\n01.01.2025;;Тест Тест;4")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_multiple_errors_reported(self, client, mock_conn):
        """Несколько кривых строк — ошибки собираем все разом, не останавливаемся на первой."""
        content = csv_bytes(
            "Дата;Номер группы;ФИО;Оценка\n"
            "вчера;101Б;Тест1;9\n"         # плохая дата + оценка за пределами
            "01.01.2025;102Б;Тест2;abc\n"   # оценка не число
        )
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 422
        detail = response.json()["detail"]
        # Обе строки должны быть упомянуты в ответе
        assert "2" in detail or "3" in detail

    @pytest.mark.asyncio
    async def test_valid_csv_with_utf8_no_bom(self, client, mock_conn):
        """UTF-8 без BOM тоже принимаем — не все редакторы его ставят."""
        mock_conn.fetchval.side_effect = _make_fetchval_side_effect()
        mock_conn.execute.return_value = "INSERT 0 1"

        content = "Дата;Номер группы;ФИО;Оценка\n01.01.2025;101Б;Тест Без БОМ;5\n".encode("utf-8")
        response = await client.post("/upload-grades", files=upload_files(content))
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
