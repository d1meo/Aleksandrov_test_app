from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг из переменных окружения"""

    database_url: str
    max_upload_size_mb: int = 10  # Максимальный размер файла в MB

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Один инстанс на весь проект — импортируй отсюда и не выдумывай.
settings = Settings()
