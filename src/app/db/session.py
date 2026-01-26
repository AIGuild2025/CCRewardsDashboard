from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Do not log SQL statement parameters by default (can contain sensitive data).
#
# Even if someone accidentally sets DB_ECHO=true in non-dev, keep it off to avoid
# logging queries/params in shared environments.
async_engine = create_async_engine(
    settings.database_url,
    echo=(settings.db_echo if settings.app_env.lower() == "development" else False),
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
