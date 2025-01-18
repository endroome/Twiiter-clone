from sqlalchemy.ext.asyncio import (  # type: ignore # noqa: E501
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://admin:admin@postgres_db"  # Prod
# DATABASE_URL = "postgresql+asyncpg://test:test@db:5432/test"  # Testing

engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_async_session() -> AsyncSession:  # type: ignore
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()   # type: ignore
