from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)

# Без этого после commit() обращение к полям модели в async падает с MissingGreenlet.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: одна сессия БД на один HTTP-запрос.

    commit() вызывают сервисы. Незакоммиченное откатывается при закрытии сессии.
    """
    async with SessionLocal() as session:
        yield session
