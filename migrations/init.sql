-- =========================================================
-- Инициализация базы данных — создаём таблицы с нуля
-- =========================================================

-- Справочник студентов.
-- Уникальность — по связке ФИО + группа, это покрывает случай
-- когда однофамильцы учатся в разных группах.
CREATE TABLE IF NOT EXISTS students (
    id           SERIAL PRIMARY KEY,
    full_name    VARCHAR(255) NOT NULL,
    group_number VARCHAR(20)  NOT NULL,
    CONSTRAINT uq_students_name_group UNIQUE (full_name, group_number)
);

-- Оценки студентов.
-- Одна строка CSV = одна строка таблицы.
-- Дубли при повторной загрузке тихо скипаются через ON CONFLICT DO NOTHING
-- (уникальность по паре студент + дата).
CREATE TABLE IF NOT EXISTS grades (
    id         SERIAL PRIMARY KEY,
    student_id INTEGER    NOT NULL REFERENCES students (id) ON DELETE CASCADE,
    grade      SMALLINT   NOT NULL CHECK (grade BETWEEN 1 AND 5),
    date       DATE       NOT NULL,
    CONSTRAINT uq_grades_student_date UNIQUE (student_id, date)
);

-- Индексы для аналитических запросов — без них будет грустно на больших данных.
CREATE INDEX IF NOT EXISTS idx_grades_student_id ON grades (student_id);
CREATE INDEX IF NOT EXISTS idx_grades_grade      ON grades (grade);
