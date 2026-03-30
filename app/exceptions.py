"""
Доменные исключения для сервисного слоя.
"""


class ServiceError(Exception):
    """Базовая ошибка сервисного слоя."""
    pass


class DatabaseError(ServiceError):
    """Ошибка базы данных."""
    pass


class ValidationError(ServiceError):
    """Ошибка валидации данных."""
    pass