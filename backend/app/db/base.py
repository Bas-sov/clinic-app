from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс всех моделей SQLAlchemy.

    Схема БД создаётся только из db/schema.sql.
    Base.metadata.create_all() не вызываем: модели лишь описывают
    уже существующие таблицы, а не создают их.
    """
