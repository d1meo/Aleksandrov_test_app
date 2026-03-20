from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг из переменных окружения — никаких хардкодов"""

    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Один инстанс на весь проект — импортируй отсюда и не выдумывай.
settings = Settings()
