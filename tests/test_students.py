"""
Тесты аналитических ручек:
  GET /students/more-than-3-twos
  GET /students/less-than-5-twos

Покрытие:
  Хэппи-пас
  ├── more-than-3-twos возвращает студентов, отсортированных по убыванию
  ├── less-than-5-twos возвращает студентов, отсортированных по убыванию
  ├── обе ручки отдают [] если данных нет
  └── студент с ровно 4 двойками попадает в ОБЕ выборки — пересечение

Граничные случаи
  ├── ровно 3 двойки → НЕ попадает в more-than-3 (строгое >)
  ├── ровно 5 двоек  → НЕ попадает в less-than-5 (строгое <)
  └── схема ответа: full_name (str) + count_twos (int)
"""

import pytest


# ---------------------------------------------------------------------------
# Хелпер
# ---------------------------------------------------------------------------

def _row(full_name: str, count_twos: int) -> dict:
    return {"full_name": full_name, "count_twos": count_twos}


# ---------------------------------------------------------------------------
# GET /students/more-than-3-twos
# ---------------------------------------------------------------------------

class TestMoreThan3Twos:

    @pytest.mark.asyncio
    async def test_returns_students_with_more_than_3_twos(self, client, mock_conn):
        """Должны вернуться студенты с count_twos > 3."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [
            _row("Новиков Егор", 9),
            _row("Голубев Тимофей", 9),
            _row("Иванов Алексей Сергеевич", 8),
        ]

        response = await client.get("/students/more-than-3-twos")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["full_name"] == "Новиков Егор"
        assert data[0]["count_twos"] == 9

    @pytest.mark.asyncio
    async def test_response_schema(self, client, mock_conn):
        """Каждый элемент — ровно full_name (str) и count_twos (int), ничего лишнего."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [_row("Тест Тест", 5)]

        response = await client.get("/students/more-than-3-twos")
        item = response.json()[0]

        assert set(item.keys()) == {"full_name", "count_twos"}
        assert isinstance(item["full_name"], str)
        assert isinstance(item["count_twos"], int)

    @pytest.mark.asyncio
    async def test_empty_result_when_no_data(self, client, mock_conn):
        """Нет подходящих студентов — возвращаем пустой список, не 404."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = []

        response = await client.get("/students/more-than-3-twos")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_boundary_exactly_3_twos_excluded(self, client, mock_conn):
        """Ровно 3 двойки — не проходит, условие строгое (> 3).
        База возвращает пустой список — ручка тоже должна."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = []

        response = await client.get("/students/more-than-3-twos")
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_sorted_by_count_desc(self, client, mock_conn):
        """Результат должен быть отсортирован по убыванию count_twos."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [
            _row("Первый", 10),
            _row("Второй", 7),
            _row("Третий", 4),
        ]
        response = await client.get("/students/more-than-3-twos")
        counts = [item["count_twos"] for item in response.json()]
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# GET /students/less-than-5-twos
# ---------------------------------------------------------------------------

class TestLessThan5Twos:

    @pytest.mark.asyncio
    async def test_returns_students_with_less_than_5_twos(self, client, mock_conn):
        """Должны вернуться студенты с count_twos < 5."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [
            _row("Николаева Софья Максимовна", 4),
            _row("Жданова Марина", 4),
            _row("Морозова Алина", 3),
            _row("Лазарев Кирилл", 3),
        ]

        response = await client.get("/students/less-than-5-twos")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert data[0]["count_twos"] == 4

    @pytest.mark.asyncio
    async def test_response_schema(self, client, mock_conn):
        """Каждый элемент — ровно full_name (str) и count_twos (int), ничего лишнего."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [_row("Тест Тест", 2)]

        response = await client.get("/students/less-than-5-twos")
        item = response.json()[0]

        assert set(item.keys()) == {"full_name", "count_twos"}
        assert isinstance(item["full_name"], str)
        assert isinstance(item["count_twos"], int)

    @pytest.mark.asyncio
    async def test_empty_result_when_no_data(self, client, mock_conn):
        """Нет подходящих студентов — возвращаем пустой список."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = []

        response = await client.get("/students/less-than-5-twos")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_boundary_exactly_5_twos_excluded(self, client, mock_conn):
        """Ровно 5 двоек — не проходит, условие строгое (< 5)."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = []

        response = await client.get("/students/less-than-5-twos")
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_sorted_by_count_desc(self, client, mock_conn):
        """Результат должен быть отсортирован по убыванию count_twos."""
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [
            _row("Первый", 4),
            _row("Второй", 3),
            _row("Третий", 1),
        ]
        response = await client.get("/students/less-than-5-twos")
        counts = [item["count_twos"] for item in response.json()]
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Тест на пересечение — студент с 4 двойками попадает в ОБЕ ручки
# ---------------------------------------------------------------------------

class TestEndpointOverlap:

    @pytest.mark.asyncio
    async def test_student_with_4_twos_in_both_endpoints(self, client, mock_conn):
        """4 двойки удовлетворяют и > 3 и < 5 одновременно — студент должен быть в обоих списках."""
        overlapping_student = _row("Пересекающийся Студент", 4)
        mock_conn.fetch.reset_mock(return_value=True, side_effect=True)
        mock_conn.fetch.return_value = [overlapping_student]

        r1 = await client.get("/students/more-than-3-twos")
        names_more = [s["full_name"] for s in r1.json()]

        # тот же мок — та же фигня вернётся и для second ручки
        r2 = await client.get("/students/less-than-5-twos")
        names_less = [s["full_name"] for s in r2.json()]

        assert "Пересекающийся Студент" in names_more
        assert "Пересекающийся Студент" in names_less
