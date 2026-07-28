import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from server.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./honmonit.db")

engine = create_async_engine(
    DATABASE_URL,
    echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        yield session
