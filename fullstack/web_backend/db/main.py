"""
core/database.py
----------------
Async PostgreSQL engine and session factory using SQLModel + asyncpg.

Install:
    pip install sqlmodel asyncpg "sqlalchemy[asyncio]"
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel
from core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields a DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session