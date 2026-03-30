"# Student Grades Service

REST API на **FastAPI** для загрузки и анализа успеваемости студентов.  
Данные хранятся в **PostgreSQL**, доступ к БД — исключительно через чистый SQL (asyncpg, без ORM).

---

## Стек

| Компонент | Технология |
|---|---|
| API framework | FastAPI 0.111 |
| БД | PostgreSQL 16 |
| Драйвер БД | asyncpg (async, чистый SQL) |
| Контейнеризация | Docker + Docker Compose |
| Тесты | pytest + httpx + pytest-asyncio |

---

## Быстрый старт (Docker Compose)

```bash
# 1. Клонировать репозиторий
git clone <repository_url>
cd ecom_test_app

# 2. Создать .env из шаблона
cp .env.example .env

# 3. Собрать и запустить
docker compose up --build

# API доступен на http://localhost:8000
# Swagger UI:  http://localhost:8000/docs
```

PostgreSQL автоматически инициализируется скриптом `migrations/init.sql`  
при первом запуске через `docker-entrypoint-initdb.d`.

---

## Локальный запуск (без Docker)

### Требования
- Python 3.12+
- PostgreSQL 14+
- uv (современный пакетный менеджер)

```bash
# 1. Установить uv (если еще не установлен)
curl -Ls https://astral.sh/uv/install.sh | sh

# 2. Клонировать и перейти в проект
git clone <repository_url>
cd ecom_test_app

# 3. Установить зависимости
uv sync

# 4. Создать базу данных и таблицы
psql -U postgres -c \"CREATE DATABASE grades_db;\"
psql -U postgres -d grades_db -f migrations/init.sql

# 5. Настроить переменные окружения
cp .env.example .env
# Отредактировать .env, вписать свои credentials

# 6. Запустить сервис
uv run uvicorn app.main:app --reload
```

---

## API

### `POST /upload-grades`

Загрузить CSV-файл с успеваемостью студентов.

**Формат CSV** (разделитель `;`, кодировка UTF-8 или UTF-8-BOM):
```
Дата;Номер группы;ФИО;Оценка
11.03.2025;101Б;Иванов Иван Иванович;4
```

**Ограничения:**
- Максимальный размер файла: 10MB (настраивается через `MAX_UPLOAD_SIZE_MB` в .env)
- Расширение файла: .csv

**Пример запроса:**
```bash
curl -X POST http://localhost:8000/upload-grades \\
     -F \"file=@fixtures/students_grades.csv\"
```

**Пример ответа:**
```json
{
  \"status\": \"ok\",
  \"records_loaded\": 2000,
  \"students\": 40
}
```

---

### `GET /students/more-than-3-twos`

Студенты, у которых оценка **2** встречается **более 3 раз**.

```bash
curl http://localhost:8000/students/more-than-3-twos
```

**Пример ответа:**
```json
[
  { \"full_name\": \"Новиков Егор\", \"count_twos\": 9 },
  { \"full_name\": \"Голубев Тимофей\", \"count_twos\": 9 }
]
```

---

### `GET /students/less-than-5-twos`

Студенты, у которых оценка **2** встречается **менее 5 раз** (хотя бы раз).

```bash
curl http://localhost:8000/students/less-than-5-twos
```

**Пример ответа:**
```json
[
  { \"full_name\": \"Николаева Софья Максимовна\", \"count_twos\": 4 },
  { \"full_name\": \"Жданова Марина\", \"count_twos\": 4 }
]
```

---

### `GET /health`

Проверка работоспособности сервиса и подключения к базе данных.

```bash
curl http://localhost:8000/health
```

**Пример ответа при успехе:**
```json
{
  \"status\": \"ok\",
  \"database\": \"connected\"
}
```

**Пример ответа при ошибке подключения к БД:**
```json
{
  \"detail\": \"Service unavailable. Database connection failed: ...\"
}
```

---

## Структура проекта

```
ecom_test_app/
├── app/
│   ├── main.py           # FastAPI app + lifespan + роутеры
│   ├── config.py         # Настройки (pydantic-settings, .env)
│   ├── database.py       # asyncpg connection pool с логированием
│   ├── validators.py     # Валидация CSV
│   ├── exceptions.py     # Доменные исключения
│   └── routers/
│       ├── upload.py     # POST /upload-grades (с проверкой размера файла)
│       └── students.py   # GET /students/*
├── migrations/
│   └── init.sql          # DDL: CREATE TABLE students, grades + индексы
├── tests/
│   ├── conftest.py       # Фикстуры, мок БД, async test client
│   ├── test_upload.py    # Тесты загрузки CSV (happy path + негативные)
│   ├── test_students.py  # Тесты аналитических ручек
│   └── test_validators.py # Unit-тесты валидатора CSV
├── fixtures/
│   ├── students_grades.csv  # Оригинальный CSV из задания
│   ├── grades_minimal.csv   # Минимальный тестовый CSV
│   └── grades_twos.csv      # CSV с контролируемым числом двоек
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── pyproject.toml        # Зависимости и конфигурация
├── uv.lock               # Lock-файл для воспроизводимых сборок
└── README.md
```

---

## Запуск тестов

```bash
# Тесты не требуют запущенной БД — используется мок-слой
uv run pytest -v
```

**Пример вывода:**
```
tests/test_upload.py::TestUploadHappyPath::test_upload_minimal_csv PASSED
tests/test_upload.py::TestUploadHappyPath::test_upload_full_csv PASSED
...
tests/test_validators.py::TestParseValid::test_single_valid_row PASSED
...
======= 35 passed in 1.23s =======
```

---

## Переменные окружения

| Переменная | Описание | Пример | По умолчанию |
|---|---|---|---|
| `DATABASE_URL` | DSN для подключения к PostgreSQL | `postgresql://user:pass@localhost:5432/db` | - |
| `MAX_UPLOAD_SIZE_MB` | Максимальный размер загружаемого файла (MB) | `10` | `10` |
| `POSTGRES_USER` | Пользователь PostgreSQL (для docker compose) | `grades_user` | `grades_user` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL (для docker compose) | `grades_pass` | `grades_pass` |
| `POSTGRES_DB` | Имя базы данных (для docker compose) | `grades_db` | `grades_db` |

---

## Схема базы данных

```sql
-- Справочник студентов
CREATE TABLE students (
    id           SERIAL PRIMARY KEY,
    full_name    VARCHAR(255) NOT NULL,
    group_number VARCHAR(20)  NOT NULL,
    CONSTRAINT uq_students_name_group UNIQUE (full_name, group_number)
);

-- Оценки (одна строка CSV = одна строка таблицы)
CREATE TABLE grades (
    id         SERIAL PRIMARY KEY,
    student_id INTEGER  NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    grade      SMALLINT NOT NULL CHECK (grade BETWEEN 1 AND 5),
    date       DATE     NOT NULL,
    CONSTRAINT uq_grades_student_date UNIQUE (student_id, date)
);

-- Индексы для аналитических запросов
CREATE INDEX idx_grades_student_id ON grades (student_id);
CREATE INDEX idx_grades_grade      ON grades (grade);
```

Повторная загрузка одного и того же CSV безопасна — дубликаты тихо пропускаются  
(`INSERT … ON CONFLICT DO NOTHING`).

---

## Безопасность и обработка ошибок

Проект включает следующие меры безопасности:
1. **Ограничение размера файла** (10MB по умолчанию)
2. **Параметризованные SQL-запросы** (защита от SQL-инъекций)
3. **Детальная валидация CSV** (формат, кодировка, типы данных)
4. **Логирование ошибок** базы данных и приложения
5. **Graceful degradation** при ошибках БД

Обработка ошибок:
- HTTP 413: Файл слишком большой
- HTTP 422: Ошибки валидации CSV
- HTTP 503: Сервис недоступен (проблемы с БД)
- HTTP 500: Внутренние ошибки сервиса

---

## Миграции базы данных

Для инициализации базы данных используется SQL-скрипт `migrations/init.sql`.  
В будущих версиях планируется переход на Alembic для управления миграциями.

---

## Лицензия

[Укажите лицензию при необходимости]
"