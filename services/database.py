from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings

# -----------------------------------------------------------------------------
# Database Engine
# -----------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True, 
    future=True,
)

# -----------------------------------------------------------------------------
# Session Maker
# -----------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# -----------------------------------------------------------------------------
# Declarative Base
# -----------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass

# -----------------------------------------------------------------------------
# Dependency
# -----------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to provide a database session.
    Ensures the session is closed after the request is processed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# -----------------------------------------------------------------------------
# Lifecycle Utilities
# -----------------------------------------------------------------------------
async def init_db():
    """
    Initialize database tables.
    Useful for creating tables in development.
    """
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"WARNING: Could not create tables: {e}")

async def close_db():
    """
    Close the database engine.
    Should be called on application shutdown.
    """
    await engine.dispose()